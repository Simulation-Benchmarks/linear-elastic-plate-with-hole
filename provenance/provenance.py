"""Utilities for reading, querying, plotting, and validating RO-Crate provenance.

The public entry point is :class:`ProvenanceAnalyzer`. It loads RO-Crate
JSON-LD metadata into an RDF graph, builds SPARQL queries for benchmark
parameters and metrics, plots extracted values, and validates RO-Crate folders
against the RO-Crate 1.1 profile.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib.pyplot as plt
from rdflib import Graph
from rocrate_validator import models, services

DEFAULT_METADATA_FILENAME = "ro-crate-metadata.json"


class ProvenanceAnalyzer:
    """Analyze, visualize, and validate provenance data from an RO-Crate.

    Args:
        provenance_folderpath: Folder containing the RO-Crate metadata file.
        provenance_filename: Metadata filename inside ``provenance_folderpath``.

    Attributes:
        provenance_folderpath: Folder containing the RO-Crate.
        provenance_filename: RO-Crate metadata filename.
    """

    SCHEMA_PREFIX = "PREFIX schema: <http://schema.org/>"
    FORMAL_PARAMETER_TYPE = "<https://bioschemas.org/FormalParameter>"
    FOAF_NAME = "<http://xmlns.com/foaf/0.1/name>"

    def __init__(
        self,
        provenance_folderpath: str | Path | None = None,
        provenance_filename: str = DEFAULT_METADATA_FILENAME,
    ) -> None:
        self.provenance_folderpath = provenance_folderpath
        self.provenance_filename = provenance_filename

    def _metadata_path(self) -> Path:
        """Return the metadata file path for this analyzer."""
        return self._provenance_dir() / self.provenance_filename

    def _provenance_dir(self) -> Path:
        """Return the configured RO-Crate folder path."""
        if self.provenance_folderpath is None:
            raise ValueError("provenance_folderpath must be set")
        return Path(self.provenance_folderpath)

    def load_graph_from_file(self) -> Graph:
        """Load the RO-Crate metadata JSON-LD file into an RDF graph.

        Returns:
            Parsed RDF graph containing the provenance metadata.

        Raises:
            Exception: Propagates RDF parsing errors after printing context.
        """
        metadata_path = self._metadata_path()

        try:
            graph = Graph()
            graph.parse(metadata_path, format="json-ld")
            return graph
        except Exception as error:
            print(f"Failed to parse {metadata_path}: {error}")
            raise

    @staticmethod
    def sanitize_variable_name(name: str) -> str:
        """Convert a string into a SPARQL-safe variable name."""
        variable_name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        if re.match(r"^\d", variable_name):
            variable_name = "_" + variable_name
        return variable_name or "_"

    @staticmethod
    def _sparql_string_literal(value: str) -> str:
        """Escape a Python string for safe use inside a SPARQL string literal."""
        return (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )

    def _variable_map(self, names: Iterable[str]) -> dict[str, str]:
        """Map display names to SPARQL-safe variable names."""
        return {name: self.sanitize_variable_name(name) for name in names}

    @staticmethod
    def _select_variables(names: Sequence[str], var_map: dict[str, str]) -> str:
        """Create a SPARQL SELECT variable list from display names."""
        return " ".join(f"?{var_map[name]}" for name in names)

    def _create_action_links(self, include_tool: bool = False) -> list[str]:
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
                    f"?software {self.FOAF_NAME} ?tool_name .",
                ]
            )

        return links

    def _node_type(self, node_prefix: str) -> str:
        """Return the RDF type used by a parameter or metric node."""
        if node_prefix == "param":
            return self.FORMAL_PARAMETER_TYPE
        return "schema:PropertyValue"

    def _value_block(
        self,
        parent: str,
        relation: str,
        node_prefix: str,
        name: str,
        var_map: dict[str, str],
        name_predicate: str,
    ) -> str:
        """Build a graph pattern that extracts one named value."""
        safe_name = var_map[name]
        escaped_name = self._sparql_string_literal(name)

        return f"""
        {parent} {relation} ?{node_prefix}_{safe_name} .
        ?{node_prefix}_{safe_name} a {self._node_type(node_prefix)} ;
            {name_predicate} "{escaped_name}" ;
            schema:defaultValue ?{safe_name} .
        """.strip()

    def _parameter_block(
        self,
        name: str,
        var_map: dict[str, str],
        name_predicate: str = "schema:name",
    ) -> str:
        """Build a graph pattern that extracts one configuration parameter."""
        return self._value_block(
            "?configuration",
            "schema:exampleOfWork",
            "param",
            name,
            var_map,
            name_predicate,
        )

    def _metric_block(
        self,
        name: str,
        var_map: dict[str, str],
        name_predicate: str = "schema:name",
    ) -> str:
        """Build a graph pattern that extracts one run metric."""
        return self._value_block(
            "?runAction",
            "schema:result",
            "metric",
            name,
            var_map,
            name_predicate,
        )

    @staticmethod
    def _join_blocks(*blocks: str) -> str:
        """Join non-empty SPARQL graph pattern blocks."""
        return "\n".join(block for block in blocks if block)

    @staticmethod
    def _where_block(inner_query: str, named_graph: str | None = None) -> str:
        """Optionally wrap a graph pattern in a named graph block."""
        if not named_graph:
            return inner_query
        return f"GRAPH <{named_graph}> {{\n{inner_query}\n}}"

    @staticmethod
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
        self,
        order_name: str | None,
        var_map: dict[str, str],
    ) -> str:
        """Build an ORDER BY clause for a selected parameter or metric."""
        if not order_name:
            return ""

        order_var = var_map.get(order_name, self.sanitize_variable_name(order_name))
        return f"\nORDER BY ?{order_var}"

    def _format_query(
        self,
        select_vars: str,
        where_block: str,
        order_clause: str = "",
    ) -> str:
        """Format a complete SPARQL query."""
        return f"""
        {self.SCHEMA_PREFIX}

        SELECT {select_vars}
        WHERE {{
            {where_block}
        }}
        {order_clause}
        """.strip()

    @staticmethod
    def _collect_xy_values(
        data: Sequence[Sequence[Any]],
        x_axis_index: int,
        y_axis_index: int,
    ) -> tuple[list[tuple[float, float]], list[float]]:
        """Collect sorted x/y pairs and unique x tick values from table rows."""
        values = []
        x_tick_set = set()

        for row in data:
            x_value = float(row[x_axis_index])
            y_value = float(row[y_axis_index])
            values.append((x_value, y_value))
            x_tick_set.add(x_value)

        return sorted(values), sorted(x_tick_set)

    @staticmethod
    def _finish_plot(
        x_axis_label: str,
        y_axis_label: str,
        title: str,
        x_ticks: Sequence[float],
        output_file: str | None,
    ) -> None:
        """Apply common plot formatting and save or display the result."""
        plt.xlabel(x_axis_label)
        plt.ylabel(y_axis_label)
        plt.title(title)
        plt.grid(True)
        plt.xscale("log")
        plt.xticks(ticks=x_ticks, labels=[str(x) for x in x_ticks], rotation=45)
        plt.tight_layout()

        if output_file:
            plt.savefig(output_file)
            print(f"Plot saved to: {output_file}")
        else:
            plt.show()

    def build_dynamic_rocrate_query(
        self,
        parameters: Sequence[str],
        metrics: Sequence[str],
        named_graph: str | None = None,
        order_by: str | None = None,
    ) -> str:
        """Build a SPARQL query for local aggregate RO-Crate provenance.

        The query extracts parameter values from
        ``CreateAction -> object -> PropertyValue -> exampleOfWork`` and metric
        values from ``CreateAction -> result -> PropertyValue``.

        Args:
            parameters: Parameter names matched with ``schema:name``.
            metrics: Metric names matched with ``schema:name``.
            named_graph: Optional named graph URI to query inside.
            order_by: Optional parameter or metric name used for result ordering.
                Defaults to the first parameter when available.

        Returns:
            Complete SPARQL query string.
        """
        all_names = [*parameters, *metrics]
        var_map = self._variable_map(all_names)
        select_vars = self._select_variables(all_names, var_map)

        inner_query = self._join_blocks(
            "\n".join(self._create_action_links()),
            "\n".join(self._parameter_block(name, var_map) for name in parameters),
            "\n".join(self._metric_block(name, var_map) for name in metrics),
        )

        order_name = order_by or (parameters[0] if parameters else None)
        return self._format_query(
            select_vars,
            self._where_block(inner_query, named_graph),
            self._order_clause(order_name, var_map),
        )

    def build_dynamic_rohub_query(
        self,
        parameters: Sequence[str],
        metrics: Sequence[str],
        named_graphs: Sequence[str],
    ) -> str:
        """Build a SPARQL query for provenance spread across RoHub named graphs.

        The query includes ``?tool_name`` and reads parameter/metric names using
        FOAF names, matching the uploaded RoHub graph structure.

        Args:
            parameters: Parameter names matched with FOAF name.
            metrics: Metric names matched with FOAF name.
            named_graphs: Named graph URIs included in a ``VALUES ?graph`` block.

        Returns:
            Complete SPARQL query string.
        """
        all_names = [*parameters, *metrics]
        var_map = self._variable_map(all_names)
        select_vars = " ".join(
            ["?tool_name", self._select_variables(all_names, var_map)]
        )

        inner_query = self._join_blocks(
            "\n".join(self._create_action_links(include_tool=True)),
            "\n".join(
                self._parameter_block(name, var_map, self.FOAF_NAME)
                for name in parameters
            ),
            "\n".join(
                self._metric_block(name, var_map, self.FOAF_NAME) for name in metrics
            ),
        )

        order_name = parameters[0] if parameters else None
        return self._format_query(
            select_vars,
            self._named_graph_values_block(named_graphs, inner_query),
            self._order_clause(order_name, var_map),
        )

    @staticmethod
    def run_query_on_graph(graph: Graph, query: str) -> Any:
        """Execute a SPARQL query on an RDF graph.

        Args:
            graph: RDF graph to query.
            query: SPARQL query string.

        Returns:
            Query result object returned by ``rdflib.Graph.query``.
        """
        return graph.query(query)

    def plot_provenance_graph(
        self,
        data: Sequence[Sequence[Any]],
        x_axis_label: str,
        y_axis_label: str,
        x_axis_index: int,
        y_axis_index: int,
        title: str,
        output_file: str | None = None,
        figsize: tuple[int, int] = (12, 5),
    ) -> None:
        """Plot one metric series from extracted provenance data.

        Args:
            data: Table rows containing the x and y values.
            x_axis_label: Label for the x-axis.
            y_axis_label: Label for the y-axis.
            x_axis_index: Row index for x-axis values.
            y_axis_index: Row index for y-axis values.
            title: Plot title.
            output_file: Optional output path. If omitted, the plot is shown.
            figsize: Matplotlib figure size.
        """
        values, x_ticks = self._collect_xy_values(data, x_axis_index, y_axis_index)

        plt.figure(figsize=figsize)
        x_values, y_values = zip(*values)
        plt.plot(x_values, y_values, marker="o", linestyle="-")
        self._finish_plot(x_axis_label, y_axis_label, title, x_ticks, output_file)

    def plot_provenance_graph_rohub(
        self,
        data: Sequence[Sequence[Any]],
        x_axis_label: str,
        y_axis_label: str,
        group_index: int,
        x_axis_index: int,
        y_axis_index: int,
        title: str,
        output_file: str | None = None,
        figsize: tuple[int, int] = (12, 5),
    ) -> None:
        """Plot grouped metric series from RoHub provenance query results.

        Args:
            data: Table rows containing group, x, and y values.
            x_axis_label: Label for the x-axis.
            y_axis_label: Label for the y-axis.
            group_index: Row index containing the group label.
            x_axis_index: Row index for x-axis values.
            y_axis_index: Row index for y-axis values.
            title: Plot title.
            output_file: Optional output path. If omitted, the plot is shown.
            figsize: Matplotlib figure size.
        """
        grouped_values: dict[str, list[tuple[float, float]]] = defaultdict(list)
        x_tick_set = set()

        for row in data:
            group = str(row[group_index])
            x_value = float(row[x_axis_index])
            y_value = float(row[y_axis_index])

            grouped_values[group].append((x_value, y_value))
            x_tick_set.add(x_value)

        plt.figure(figsize=figsize)

        for group, values in grouped_values.items():
            values.sort()
            x_values, y_values = zip(*values)
            plt.plot(x_values, y_values, marker="o", linestyle="-", label=group)

        if grouped_values:
            plt.legend()

        self._finish_plot(
            x_axis_label,
            y_axis_label,
            title,
            sorted(x_tick_set),
            output_file,
        )

    def validate_provenance(self) -> None:
        """Validate the RO-Crate folder against the RO-Crate 1.1 profile.

        Raises:
            AssertionError: If the validator reports required-profile issues.
        """
        settings = services.ValidationSettings(
            rocrate_uri=str(self._provenance_dir()),
            profile_identifier="ro-crate-1.1",
            requirement_severity=models.Severity.REQUIRED,
        )

        result = services.validate(settings)

        assert not result.has_issues(), "RO-Crate is invalid!\n" + "\n".join(
            f"Detected issue of severity {issue.severity.name} with check "
            f'"{issue.check.identifier}": {issue.message}'
            for issue in result.get_issues()
        )

        print("RO-Crate is valid!")
