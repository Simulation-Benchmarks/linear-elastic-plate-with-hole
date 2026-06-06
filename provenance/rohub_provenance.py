"""Helpers for querying benchmark provenance from RoHub."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import rohub

from provenance import ProvenanceAnalyzer

if TYPE_CHECKING:
    import pandas as pd


ANNOTATION_PREDICATE = "http://w3id.org/nfdi4ing/metadata4ing#investigates"
DEVELOPMENT_API_URL = "https://rohub2020-devel.apps.bst2.paas.psnc.pl/api/"
DEVELOPMENT_CLIENT_ID = "rohub2020-cli"
DEVELOPMENT_CLIENT_SECRET = "714617a7-87bc-4a88-8682-5f9c2f60337d"
DEVELOPMENT_KEYCLOAK_URL = (
    "https://keycloak-dev.apps.paas-dev.psnc.pl/auth/realms/rohub/"
    "protocol/openid-connect/token"
)
DEVELOPMENT_SPARQL_ENDPOINT = (
    "https://virtuoso-rohub2020-devel.apps.bst2.paas.psnc.pl/sparql"
)
PRODUCTION_API_URL = "https://api.rohub.org/api/"
PRODUCTION_CLIENT_ID = "rohub2020-public-cli"
PRODUCTION_KEYCLOAK_URL = (
    "https://login.rohub.org/auth/realms/rohub/protocol/openid-connect/token"
)
PRODUCTION_SPARQL_ENDPOINT = (
    "https://virtuoso-rohub2020-production.apps.bst2.paas.psnc.pl/sparql"
)


def configure_rohub(use_development_version: bool = True) -> None:
    """Configure RoHub client settings for development or production."""
    rohub.settings.SLEEP_TIME = 10

    if use_development_version:
        rohub.settings.API_URL = DEVELOPMENT_API_URL
        rohub.settings.KEYCLOAK_CLIENT_ID = DEVELOPMENT_CLIENT_ID
        rohub.settings.KEYCLOAK_CLIENT_SECRET = DEVELOPMENT_CLIENT_SECRET
        rohub.settings.KEYCLOAK_URL = DEVELOPMENT_KEYCLOAK_URL
        rohub.settings.SPARQL_ENDPOINT = DEVELOPMENT_SPARQL_ENDPOINT
        return

    rohub.settings.API_URL = PRODUCTION_API_URL
    rohub.settings.KEYCLOAK_CLIENT_ID = PRODUCTION_CLIENT_ID
    rohub.settings.KEYCLOAK_URL = PRODUCTION_KEYCLOAK_URL
    rohub.settings.SPARQL_ENDPOINT = PRODUCTION_SPARQL_ENDPOINT


def login_to_rohub(
    username: str,
    password: str,
    use_development_version: bool = True,
) -> None:
    """Configure the RoHub client and authenticate with username/password."""
    configure_rohub(use_development_version=use_development_version)
    rohub.login(username=username, password=password)


def benchmark_annotation_object(benchmark_name: str) -> str:
    """Return the benchmark annotation IRI used for uploaded RO-Crates."""
    return f"https://github.com/Simulation-Benchmarks/{benchmark_name}"


def find_benchmark_ro_uuids(benchmark_name: str) -> list[str]:
    """Find RoHub research object UUIDs annotated with a benchmark IRI."""
    query = f"""
    SELECT ?subject
    WHERE {{
      ?subject <{ANNOTATION_PREDICATE}> <{benchmark_annotation_object(benchmark_name)}> .
    }}
    """

    result = rohub.query_sparql_endpoint(
        query,
        endpoint_url=rohub.settings.SPARQL_ENDPOINT,
    )

    if result.empty:
        return []

    return [iri.rstrip("/").split("/")[-1] for iri in result["subject"]]


def find_named_graphs_for_uuids(
    uuids: Sequence[str],
    use_development_version: bool = True,
) -> dict[str, str]:
    """Find RoHub SPARQL named graphs for research object UUIDs."""
    ro_id_base = "ro-id-dev" if use_development_version else "ro-id"
    named_graphs = {}

    for uuid in uuids:
        query = f"""
        PREFIX schema: <http://schema.org/>
        SELECT ?graph WHERE {{
            GRAPH ?graph {{ <https://w3id.org/{ro_id_base}/{uuid}> a schema:Dataset . }}
        }}
        """

        result = rohub.query_sparql_endpoint(
            query,
            endpoint_url=rohub.settings.SPARQL_ENDPOINT,
        )

        if not result.empty:
            named_graphs[uuid] = result.iloc[0]["graph"]

    return named_graphs


def fetch_benchmark_metric_data(
    benchmark_name: str,
    parameters: Sequence[str],
    metrics: Sequence[str],
    use_development_version: bool = True,
) -> pd.DataFrame:
    """Fetch benchmark parameter and metric data from RoHub."""
    uuids = find_benchmark_ro_uuids(benchmark_name)
    named_graphs = find_named_graphs_for_uuids(
        uuids,
        use_development_version=use_development_version,
    )

    if not named_graphs:
        raise RuntimeError(f"No RoHub named graphs found for benchmark {benchmark_name}.")

    return query_metric_data_from_named_graphs(
        parameters=parameters,
        metrics=metrics,
        named_graphs=list(named_graphs.values()),
        benchmark_name=benchmark_name,
    )


def query_metric_data_from_named_graphs(
    parameters: Sequence[str],
    metrics: Sequence[str],
    named_graphs: Sequence[str],
    benchmark_name: str | None = None,
) -> pd.DataFrame:
    """Query benchmark parameter and metric data from resolved RoHub graphs."""
    if not named_graphs:
        message = "No RoHub named graphs provided."
        if benchmark_name:
            message = f"No RoHub named graphs found for benchmark {benchmark_name}."
        raise RuntimeError(message)

    analyzer = ProvenanceAnalyzer()
    query = analyzer.build_dynamic_rohub_query(
        parameters,
        metrics,
        named_graphs,
    )

    result = rohub.query_sparql_endpoint(
        query,
        endpoint_url=rohub.settings.SPARQL_ENDPOINT,
    )

    if result.empty:
        message = "No RoHub metric data found."
        if benchmark_name:
            message = f"No RoHub metric data found for benchmark {benchmark_name}."
        raise RuntimeError(message)

    return result


def fetch_authenticated_benchmark_metric_data(
    username: str,
    password: str,
    benchmark_name: str,
    parameters: Sequence[str],
    metrics: Sequence[str],
    use_development_version: bool = True,
) -> pd.DataFrame:
    """Authenticate with RoHub and fetch benchmark parameter/metric data."""
    login_to_rohub(
        username=username,
        password=password,
        use_development_version=use_development_version,
    )
    return fetch_benchmark_metric_data(
        benchmark_name=benchmark_name,
        parameters=parameters,
        metrics=metrics,
        use_development_version=use_development_version,
    )
