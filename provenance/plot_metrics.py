import argparse
import pandas as pd
from provenance import ProvenanceAnalyzer
from rohub_provenance import fetch_authenticated_benchmark_metric_data

def parse_args():
    """
    Parse command-line arguments for the provenance processing script.

    Returns:
        argparse.Namespace: Parsed arguments containing:
            - username: RoHub username
            - password: RoHub password
            - benchmark_name: Benchmark name used in RoHub annotations
            - tool: Optional tool name used to filter plotted data
            - output_file: Path for the final visualization output
    """
    parser = argparse.ArgumentParser(
        description="Fetch benchmark provenance from RoHub and plot simulation metrics."
    )
    parser.add_argument(
        "--output_file",
        type=str,
        required=True,
        help="Final visualization file",
    )
    parser.add_argument(
        "--username",
        type=str,
        required=True,
        help="Username for RoHub",
    )
    parser.add_argument(
        "--password",
        type=str,
        required=True,
        help="Password for RoHub",
    )
    parser.add_argument(
        "--benchmark-name",
        type=str,
        default="linear-elastic-plate-with-hole",
        help="Benchmark name used in the RoHub semantic annotation",
    )
    parser.add_argument(
        "--tool",
        type=str,
        default=None,
        help="Optional tool name used to filter RoHub results",
    )
    parser.add_argument(
        "--use-production-rohub",
        action="store_true",
        help="Use production RoHub instead of the development instance",
    )
    return parser.parse_args()


def apply_custom_filters(data: pd.DataFrame) -> pd.DataFrame:
    """
    Filter provenance data to include only first-order linear elements.

    Filters rows where isoparametric_element_degree = 1 then removes
    these filtering columns from the result.

    Args:
        data (pd.DataFrame): Input DataFrame containing isoparametric_element_degree column.

    Returns:
        pd.DataFrame: Filtered DataFrame with isoparametric_element_degree
                     columns removed and index reset.
    """
    filtered_df = data[(data["isoparametric_element_degree"].astype(str) == "1")]

    return filtered_df.drop(columns=["isoparametric_element_degree"]).reset_index(
        drop=True
    )


def filter_by_tool(data: pd.DataFrame, tool: str | None) -> pd.DataFrame:
    """
    Filter RoHub query results by tool name.

    Args:
        data (pd.DataFrame): RoHub query results with a tool_name column.
        tool (str | None): Tool name to match case-insensitively.

    Returns:
        pd.DataFrame: Filtered rows, or the original data when no tool is given.
    """
    if not tool:
        return data

    filtered_df = data[
        data["tool_name"].astype(str).str.lower() == tool.strip().lower()
    ].reset_index(drop=True)

    assert len(filtered_df), f"No RoHub data found for tool '{tool}'."
    return filtered_df


def load_and_query_rohub(args, parameters, metrics):
    """
    Authenticate with RoHub and query benchmark provenance data.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        parameters (list): List of parameter names to query.
        metrics (list): List of metric names to query.

    Returns:
        pd.DataFrame: DataFrame containing the RoHub query results.
    """
    provenance_df = fetch_authenticated_benchmark_metric_data(
        username=args.username,
        password=args.password,
        benchmark_name=args.benchmark_name,
        parameters=parameters,
        metrics=metrics,
        use_development_version=not args.use_production_rohub,
    )

    return filter_by_tool(provenance_df, args.tool)


def plot_results(analyzer, final_df, output_file):
    """
    Generate a visualization plot of the provenance results.

    Creates a scatter/line plot showing the relationship between element size
    and maximum von Mises stress.

    Args:
        analyzer (ProvenanceAnalyzer): Initialized analyzer instance.
        final_df (pd.DataFrame): DataFrame containing filtered data to plot.
                                Expected columns: element_size,
                                max_von_mises_stress (in that order).
        output_file (str): Path where the plot image will be saved.
    """
    
    analyzer.plot_provenance_graph_rohub(
        data=final_df.values.tolist(),
        x_axis_label="Element Size",
        y_axis_label="Max Von Mises Stress",
        group_index=0,
        x_axis_index=1,
        y_axis_index=2,
        title="Element Size vs Max Von Mises Stress",
        output_file=output_file,
    )


def run(args, parameters, metrics):
    """
    Execute the complete provenance analysis workflow.

    Performs the following steps:
    1. Initialize the ProvenanceAnalyzer
    2. Fetch benchmark provenance from RoHub
    3. Filter the RoHub rows for first-order linear elements
    4. Generate visualization plot

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        parameters (list): List of parameter names to extract.
        metrics (list): List of metric names to extract.
        tools (list): List of tool names to process.
    """

    analyzer = ProvenanceAnalyzer()

    provenance_df = load_and_query_rohub(args, parameters, metrics)

    final_df = apply_custom_filters(provenance_df)

    plot_results(analyzer, final_df, args.output_file)


def main():
    """
    Main entry point for the provenance analysis script.

    Parses command-line arguments, defines the parameters and metrics to extract,
    retrieves tool names from the workflow configuration, and executes the analysis
    workflow.
    """
    args = parse_args()

    parameters = ["element_size","isoparametric_element_degree"]
    metrics = ["max_von_mises_stress"]

    run(args, parameters, metrics)


if __name__ == "__main__":
    main()
