import os
import re
from collections import defaultdict
from typing import List, Tuple

import matplotlib.pyplot as plt
from rdflib import Graph
from rocrate_validator import models, services


class ProvenanceAnalyzer:
    """
    A class to analyze, validate, and visualize provenance data from RO-Crate metadata files.

    This class loads RO-Crate JSON-LD files, builds dynamic SPARQL queries to extract
    workflow metadata about methods, parameters, and metrics, and provides visualization
    capabilities. It also validates RO-Crate files against the RO-Crate 1.1 profile.

    Attributes:
        provenance_folderpath (str): The directory path containing the RO-Crate folder.
        provenance_filename (str): The name of the provenance file (default: 'ro-crate-metadata.json').
    """

    SCHEMA_PREFIX = "PREFIX schema: <http://schema.org/>"
    FORMAL_PARAMETER_TYPE = "<https://bioschemas.org/FormalParameter>"
    FOAF_NAME = "<http://xmlns.com/foaf/0.1/name>"

    def __init__(
        self,
        provenance_folderpath: str = None,
        provenance_filename: str = "ro-crate-metadata.json",
    ):
        """
        Initialize the ProvenanceAnalyzer.

        Args:
            provenance_folderpath (str, optional): Path to the folder containing the RO-Crate.
                                                   Defaults to None.
            provenance_filename (str, optional): Name of the RO-Crate metadata file.
                                                 Defaults to "ro-crate-metadata.json".
        """
        self.provenance_folderpath = provenance_folderpath
        self.provenance_filename = provenance_filename

    def _metadata_path(self) -> str:
        return os.path.join(self.provenance_folderpath, self.provenance_filename)

    def load_graph_from_file(self) -> Graph:
        """
        Loads the RO-Crate metadata file into an rdflib Graph object.

        Returns:
            rdflib.Graph: The loaded RDF graph containing the provenance data.

        Raises:
            Exception: If the file cannot be parsed as JSON-LD.
        """
        try:
            graph = Graph()
            graph.parse(self._metadata_path(), format="json-ld")
            return graph
        except Exception as e:
            print(f"Failed to parse {self.provenance_filename}: {e}")
            raise

    def sanitize_variable_name(self, name: str) -> str:
        """
        Convert a string into a valid SPARQL variable name.

        Replaces invalid characters with underscores and ensures the variable
        name doesn't start with a digit.

        Args:
            name (str): The original string to convert.

        Returns:
            str: A sanitized variable name safe for use in SPARQL queries.
        """
        var = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        if re.match(r"^\d", var):
            var = "_" + var
        return var or "_"

    def _sparql_string_literal(self, value: str) -> str:
        """
        Escape a Python string for safe use as a SPARQL string literal.
        """
        return (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )

    def _variable_map(self, names):
        return {name: self.sanitize_variable_name(name) for name in names}

    def _select_variables(self, names, var_map):
        return " ".join(f"?{var_map[name]}" for name in names)

    def _create_action_links(self, include_tool=False):
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

    def _node_type(self, node_prefix):
        if node_prefix == "param":
            return self.FORMAL_PARAMETER_TYPE
        return "schema:PropertyValue"

    def _value_block(self, parent, relation, node_prefix, name, var_map, name_predicate):
        safe_name = var_map[name]
        escaped_name = self._sparql_string_literal(name)

        return f"""
        {parent} {relation} ?{node_prefix}_{safe_name} .
        ?{node_prefix}_{safe_name} a {self._node_type(node_prefix)} ;
            {name_predicate} "{escaped_name}" ;
            schema:defaultValue ?{safe_name} .
        """.strip()

    def _parameter_block(self, name, var_map, name_predicate="schema:name"):
        return self._value_block(
            "?configuration",
            "schema:exampleOfWork",
            "param",
            name,
            var_map,
            name_predicate,
        )

    def _metric_block(self, name, var_map, name_predicate="schema:name"):
        return self._value_block(
            "?runAction",
            "schema:result",
            "metric",
            name,
            var_map,
            name_predicate,
        )

    def _join_blocks(self, *blocks):
        return "\n".join(block for block in blocks if block)

    def _where_block(self, inner_query, named_graph=None):
        if not named_graph:
            return inner_query
        return f"GRAPH <{named_graph}> {{\n{inner_query}\n}}"

    def _named_graph_values_block(self, named_graphs, inner_query):
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

    def _order_clause(self, order_name, var_map):
        if not order_name:
            return ""

        order_var = var_map.get(order_name, self.sanitize_variable_name(order_name))
        return f"\nORDER BY ?{order_var}"

    def _format_query(self, select_vars, where_block, order_clause=""):
        return f"""
        {self.SCHEMA_PREFIX}

        SELECT {select_vars}
        WHERE {{
            {where_block}
        }}
        {order_clause}
        """.strip()

    def _collect_xy_values(self, data, x_axis_index, y_axis_index):
        values = []
        x_tick_set = set()

        for row in data:
            x = float(row[x_axis_index])
            y = float(row[y_axis_index])
            values.append((x, y))
            x_tick_set.add(x)

        return sorted(values), sorted(x_tick_set)

    def _finish_plot(self, x_axis_label, y_axis_label, title, x_ticks, output_file):
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
        parameters,
        metrics,
        named_graph=None,
        order_by=None,
    ):
        """
        Generate a dynamic SPARQL query for the schema.org CreateAction structure
        used by the newer RO-Crate provenance output.

        The query extracts run parameters from:
            CreateAction -> schema:object -> PropertyValue -> schema:exampleOfWork

        and metrics from:
            CreateAction -> schema:result -> PropertyValue

        Args:
            parameters (list): Parameter names matched via schema:name.
            metrics (list): Metric names matched via schema:name.
            named_graph (str, optional): URI of a named graph to query within.
            order_by (str, optional): Parameter or metric name to order results by.
                                     Defaults to the first parameter, if available.

        Returns:
            str: A complete SPARQL query string ready to execute.
        """

        all_names = parameters + metrics
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
        parameters,
        metrics,
        named_graphs):
        """
        Generate a dynamic SPARQL query for schema.org CreateAction structure
        across multiple named graphs using VALUES ?graph.

        Also extracts:
            ?tool_name
        from:
            ?software a schema:SoftwareApplication ;
                      foaf:name ?tool_name .
        """

        all_names = parameters + metrics
        var_map = self._variable_map(all_names)
        select_vars_str = " ".join(
            ["?tool_name", self._select_variables(all_names, var_map)]
        )

        inner_query = self._join_blocks(
            "\n".join(self._create_action_links(include_tool=True)),
            "\n".join(
                self._parameter_block(name, var_map, self.FOAF_NAME)
                for name in parameters
            ),
            "\n".join(
                self._metric_block(name, var_map, self.FOAF_NAME)
                for name in metrics
            ),
        )

        order_name = parameters[0] if parameters else None
        return self._format_query(
            select_vars_str,
            self._named_graph_values_block(named_graphs, inner_query),
            self._order_clause(order_name, var_map),
        )

    def run_query_on_graph(
        self, graph: Graph, query: str
    ) -> Tuple[List[str], List[List]]:
        """
        Executes a SPARQL query on the provided RDF graph.

        Args:
            graph (rdflib.Graph): The RDF graph to query.
            query (str): The SPARQL query string to execute.

        Returns:
            rdflib.plugins.sparql.processor.SPARQLResult: The query results object
                                                          from rdflib.
        """
        return graph.query(query)

    def plot_provenance_graph(
        self,
        data: List[List],
        x_axis_label: str,
        y_axis_label: str,
        x_axis_index: str,
        y_axis_index: str,
        title: str,
        output_file: str = None,
        figsize: Tuple[int, int] = (12, 5),
    ):
        """
        Generates a scatter/line plot from the extracted provenance data.

        The plot displays data points as a single line series. The x-axis uses a
        logarithmic scale.

        Args:
            data (List[List]): The table data to plot, where each row is a list of values.
            x_axis_label (str): Label for the x-axis.
            y_axis_label (str): Label for the y-axis.
            x_axis_index (int or str): Index or key for the x-axis values in each row.
            y_axis_index (int or str): Index or key for the y-axis values in each row.
            title (str): Title of the plot.
            output_file (str, optional): Path where the plot will be saved as an image.
                                        If None, displays the plot. Defaults to None.
            figsize (Tuple[int, int], optional): Figure dimensions (width, height).
                                                Defaults to (12, 5).
        """
        values, x_ticks = self._collect_xy_values(data, x_axis_index, y_axis_index)

        plt.figure(figsize=figsize)
        x_vals, y_vals = zip(*values)
        plt.plot(x_vals, y_vals, marker="o", linestyle="-")
        self._finish_plot(x_axis_label, y_axis_label, title, x_ticks, output_file)

    def plot_provenance_graph_rohub(
        self,
        data: List[List],
        x_axis_label: str,
        y_axis_label: str,
        group_index: int,
        x_axis_index: int,
        y_axis_index: int,
        title: str,
        output_file: str = None,
        figsize: Tuple[int, int] = (12, 5),
    ):
        """
        Generates grouped scatter/line plots from provenance data.

        Expected row format example:
            ["A", x1, y1]
            ["A", x2, y2]
            ["B", x3, y3]

        Each unique group gets its own plotted line.

        Args:
            data (List[List]): Table data.
            x_axis_label (str): Label for x-axis.
            y_axis_label (str): Label for y-axis.
            group_index (int): Index containing the grouping string.
            x_axis_index (int): Index for x-axis values.
            y_axis_index (int): Index for y-axis values.
            title (str): Plot title.
            output_file (str, optional): File path to save plot.
            figsize (Tuple[int, int], optional): Figure size.
        """
        grouped_values = defaultdict(list)
        x_tick_set = set()

        for row in data:
            group = str(row[group_index])
            x = float(row[x_axis_index])
            y = float(row[y_axis_index])

            grouped_values[group].append((x, y))
            x_tick_set.add(x)

        x_ticks = sorted(x_tick_set)

        plt.figure(figsize=figsize)

        for group, values in grouped_values.items():
            values.sort()
            x_vals, y_vals = zip(*values)
            plt.plot(x_vals, y_vals, marker="o", linestyle="-", label=group)

        if grouped_values:
            plt.legend()
        self._finish_plot(x_axis_label, y_axis_label, title, x_ticks, output_file)

    def validate_provenance(self):
        """
        Validates the RO-Crate against the RO-Crate 1.1 profile.
        Uses the rocrate-validator library to check if the RO-Crate metadata
        conforms to the RO-Crate 1.1 specification with required severity level.
        Raises:
            AssertionError: If the RO-Crate has validation issues, with details
                           about each issue's severity and message.

        Prints:
            Success message if the RO-Crate is valid.
        """
        settings = services.ValidationSettings(
            rocrate_uri=self.provenance_folderpath,
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
