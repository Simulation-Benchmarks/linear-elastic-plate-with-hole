"""Helpers for querying benchmark provenance from RoHub."""

from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
import re
from typing import Iterable


CONFIG_DIR = Path(__file__).resolve().parent


def _load_json_config(filename: str) -> dict:
    """Load a JSON config file from the provenance package directory."""
    with (CONFIG_DIR / filename).open(encoding="utf-8") as config_file:
        return json.load(config_file)


ROHUB_CONFIG = _load_json_config("rohub_config.json")
ANNOTATION_CONFIG = _load_json_config("annotation_config.json")
ANNOTATION_PREDICATE = ANNOTATION_CONFIG["predicate"]


SCHEMA_PREFIX = "PREFIX schema: <http://schema.org/>"
FORMAL_PARAMETER_TYPE = "<https://bioschemas.org/FormalParameter>"
FOAF_NAME = "<http://xmlns.com/foaf/0.1/name>"


def _rohub_client():
    """Import and return the RoHub client only when network operations need it."""
    import rohub

    return rohub


def sanitize_variable_name(name: str) -> str:
    """Convert a string into a SPARQL-safe variable name."""
    variable_name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if re.match(r"^\d", variable_name):
        variable_name = "_" + variable_name
    return variable_name or "_"


def _sparql_string_literal(value: str) -> str:
    """Escape a Python string for safe use inside a SPARQL string literal."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def _variable_map(names: Iterable[str]) -> dict[str, str]:
    """Map display names to SPARQL-safe variable names."""
    return {name: sanitize_variable_name(name) for name in names}


def _select_variables(names: Sequence[str], var_map: dict[str, str]) -> str:
    """Create a SPARQL SELECT variable list from display names."""
    return " ".join(f"?{var_map[name]}" for name in names)


def _create_action_links(include_tool: bool = False) -> list[str]:
    """Build the common CreateAction graph pattern."""
    links = [
        "?runAction a schema:CreateAction .",
        "?runAction schema:object ?configuration .",
        "?configuration a schema:PropertyValue .",
    ]

    if include_tool:
        links.extend(
            [
                "?software a schema:SoftwareApplication .",
                f"?software {FOAF_NAME} ?tool_name .",
            ]
        )

    return links


def _node_type(node_prefix: str) -> str:
    """Return the RDF type used by a parameter or metric node."""
    if node_prefix == "param":
        return FORMAL_PARAMETER_TYPE
    return "schema:PropertyValue"


def _value_block(
    parent: str,
    relation: str,
    node_prefix: str,
    name: str,
    var_map: dict[str, str],
    name_predicate: str,
) -> str:
    """Build a graph pattern that extracts one named value."""
    safe_name = var_map[name]
    escaped_name = _sparql_string_literal(name)

    return f"""
    {parent} {relation} ?{node_prefix}_{safe_name} .
    ?{node_prefix}_{safe_name} a {_node_type(node_prefix)} ;
        {name_predicate} "{escaped_name}" ;
        schema:defaultValue ?{safe_name} .
    """.strip()


def _parameter_block(
    name: str,
    var_map: dict[str, str],
    name_predicate: str = "schema:name",
) -> str:
    """Build a graph pattern that extracts one configuration parameter."""
    return _value_block(
        "?configuration",
        "schema:exampleOfWork",
        "param",
        name,
        var_map,
        name_predicate,
    )


def _metric_block(
    name: str,
    var_map: dict[str, str],
    name_predicate: str = "schema:name",
) -> str:
    """Build a graph pattern that extracts one run metric."""
    return _value_block(
        "?runAction",
        "schema:result",
        "metric",
        name,
        var_map,
        name_predicate,
    )


def _join_blocks(*blocks: str) -> str:
    """Join non-empty SPARQL graph pattern blocks."""
    return "\n".join(block for block in blocks if block)


def _named_graph_values_block(
    named_graphs: Sequence[str],
    inner_query: str,
) -> str:
    """Wrap a query in ``VALUES ?graph`` and ``GRAPH ?graph`` clauses."""
    if not named_graphs:
        return inner_query

    values_block = "VALUES ?graph {\n" + "\n".join(
        f"    <{graph}>" for graph in named_graphs
    ) + "\n}"

    return f"""
    {values_block}

    GRAPH ?graph {{
        {inner_query}
    }}
    """.strip()


def _order_clause(
    order_name: str | None,
    var_map: dict[str, str],
) -> str:
    """Build an ORDER BY clause for a selected parameter or metric."""
    if not order_name:
        return ""

    order_var = var_map.get(order_name, sanitize_variable_name(order_name))
    return f"\nORDER BY ?{order_var}"


def _format_query(
    select_vars: str,
    where_block: str,
    order_clause: str = "",
) -> str:
    """Format a complete SPARQL query."""
    return f"""
    {SCHEMA_PREFIX}

    SELECT {select_vars}
    WHERE {{
        {where_block}
    }}
    {order_clause}
    """.strip()


def build_dynamic_query(
    parameters: Sequence[str],
    metrics: Sequence[str],
    named_graphs: Sequence[str],
) -> str:
    """Build a SPARQL query for provenance spread across RoHub named graphs."""
    all_names = [*parameters, *metrics]
    var_map = _variable_map(all_names)
    select_vars = " ".join(["?tool_name", _select_variables(all_names, var_map)])

    inner_query = _join_blocks(
        "\n".join(_create_action_links(include_tool=True)),
        "\n".join(
            _parameter_block(name, var_map, FOAF_NAME) for name in parameters
        ),
        "\n".join(_metric_block(name, var_map, FOAF_NAME) for name in metrics),
    )

    order_name = parameters[0] if parameters else None
    return _format_query(
        select_vars,
        _named_graph_values_block(named_graphs, inner_query),
        _order_clause(order_name, var_map),
    )


def configure_rohub(use_development_version: bool = True) -> None:
    """Configure RoHub client settings for development or production."""
    environment = "development" if use_development_version else "production"
    config = ROHUB_CONFIG[environment]
    rohub = _rohub_client()

    rohub.settings.SLEEP_TIME = ROHUB_CONFIG["sleep_time"]
    rohub.settings.API_URL = config["api_url"]
    rohub.settings.KEYCLOAK_CLIENT_ID = config["keycloak_client_id"]
    rohub.settings.KEYCLOAK_URL = config["keycloak_url"]
    rohub.settings.SPARQL_ENDPOINT = config["sparql_endpoint"]

    if "keycloak_client_secret" in config:
        rohub.settings.KEYCLOAK_CLIENT_SECRET = config["keycloak_client_secret"]


def login_to_rohub(
    username: str,
    password: str,
    use_development_version: bool = True,
) -> None:
    """Configure the RoHub client and authenticate with username/password."""
    configure_rohub(use_development_version=use_development_version)
    rohub = _rohub_client()
    rohub.login(username=username, password=password)


def benchmark_annotation_object(benchmark_name: str) -> str:
    """Return the benchmark annotation IRI used for uploaded RO-Crates."""
    return f"{ANNOTATION_CONFIG['benchmark_base_url']}/{benchmark_name}"


def build_benchmark_ro_uuids_query(benchmark_name: str) -> str:
    """Build a query for research objects annotated with a benchmark IRI."""
    return f"""
    SELECT ?subject
    WHERE {{
      ?subject <{ANNOTATION_PREDICATE}> <{benchmark_annotation_object(benchmark_name)}> .
    }}
    """


def query_sparql(query: str):
    """Run a SPARQL query against the configured RoHub endpoint."""
    rohub = _rohub_client()
    return rohub.query_sparql_endpoint(
        query,
        endpoint_url=rohub.settings.SPARQL_ENDPOINT,
    )


def build_named_graph_query(
    uuid: str,
    use_development_version: bool = True,
) -> str:
    """Build a query for the SPARQL named graph of a research object UUID."""
    environment = "development" if use_development_version else "production"
    ro_id_base = ROHUB_CONFIG[environment]["ro_id_base"]

    return f"""
    PREFIX schema: <http://schema.org/>
    SELECT ?graph WHERE {{
        GRAPH ?graph {{ <https://w3id.org/{ro_id_base}/{uuid}> a schema:Dataset . }}
    }}
    """


def query_metric_data_from_named_graphs(
    parameters: Sequence[str],
    metrics: Sequence[str],
    named_graphs: Sequence[str],
):
    """Query benchmark parameter and metric data from resolved RoHub graphs."""
    if not named_graphs:
        raise RuntimeError("No RoHub named graphs provided.")

    query = build_dynamic_query(
        parameters,
        metrics,
        named_graphs,
    )

    return query_sparql(query)
