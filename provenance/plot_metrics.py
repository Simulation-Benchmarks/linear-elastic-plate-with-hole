import argparse
import colorsys
import hashlib
import logging
from collections import defaultdict
from typing import Any, Callable, Sequence

import matplotlib.pyplot as plt
import pandas as pd
from semantic_benchmark.rohub import load_benchmark_metric_data

LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"
LOGGER = logging.getLogger(__name__)

# Fixed, CVD-checked 8-hue categorical palette (validated for adjacent-pair
# separation on a light surface). Colors are assigned to series by a stable
# hash of the series' identity (see `_assign_colors`), not by the order series
# happen to appear in the fetched data -- so a given tool/series always gets
# the same color across notebook re-runs, regardless of how many other RO-Crates
# are present or in what order RoHub returns them.
_CATEGORICAL_PALETTE = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]
_LINESTYLES = ["-", "--", "-.", ":"]
_MARKERS = ["o", "s", "^", "D", "v", "P"]


def _stable_hash(label: str) -> int:
    """Deterministic, cross-run-stable hash of a label.

    Python's built-in hash() is randomized per-process for strings (unless
    PYTHONHASHSEED is fixed), which is what made earlier color assignment
    effectively random across notebook runs. This uses a content hash instead.
    """
    digest = hashlib.md5(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _split_group_label(group: str) -> tuple[str, str]:
    """Split a "Primary, extra=value, ..." label into (primary, remainder).

    `select_plot_columns` folds any parameters beyond the first into the group
    label as ", name=value" suffixes; the primary identity (e.g. the tool name)
    always comes first.
    """
    primary, _, remainder = group.partition(", ")
    return primary, remainder


def _assign_colors(labels: Sequence[str]) -> dict[str, str]:
    """Assign a stable, collision-avoiding color to each distinct label.

    Each label's *preferred* slot is a content hash, so the same label maps to
    the same slot regardless of what other labels are present. When two labels
    prefer the same slot and both fit within the palette, the runner-up is
    bumped to its next preferred slot (probed deterministically) so that, up
    to 8 concurrent series, colors stay distinct. Beyond 8 distinct labels,
    slots repeat and a hashed color-wheel hue is used to still differentiate
    them somewhat, matching the palette's documented series cap.
    """
    n_slots = len(_CATEGORICAL_PALETTE)
    assigned: dict[str, str] = {}
    slot_taken: dict[int, str] = {}

    for label in sorted(labels):  # stable tie-break order, independent of fetch order
        base = _stable_hash(label)
        if len(assigned) < n_slots:
            for probe in range(n_slots):
                slot = (base + probe) % n_slots
                if slot not in slot_taken:
                    slot_taken[slot] = label
                    assigned[label] = _CATEGORICAL_PALETTE[slot]
                    break
        else:
            # Overflow beyond the validated 8-series cap: fall back to a
            # hashed hue so extra series are still distinguishable, even
            # though they're no longer CVD-guaranteed.
            hue = (base % 360) / 360.0
            r, g, b = colorsys.hls_to_rgb(hue, 0.5, 0.65)
            assigned[label] = "#{:02x}{:02x}{:02x}".format(
                int(r * 255), int(g * 255), int(b * 255)
            )

    return assigned


def finish_plot(
    x_axis_label: str,
    y_axis_label: str,
    title: str,
    x_ticks: Sequence[float],
    output_file: str | None,
    log_y: bool = False,
) -> None:
    """Apply common plot formatting and save or display the result."""
    plt.xlabel(x_axis_label)
    plt.ylabel(y_axis_label)
    plt.title(title)
    plt.grid(True)
    plt.xscale("log")
    if log_y:
        plt.yscale("log")
    plt.xticks(ticks=x_ticks, labels=[str(x) for x in x_ticks], rotation=45)
    plt.tight_layout()

    if output_file:
        plt.savefig(output_file)
        LOGGER.info("Plot saved to: %s", output_file)
    else:
        plt.show()


def plot_provenance_graph(
    data: Sequence[Sequence[Any]],
    x_axis_label: str,
    y_axis_label: str,
    title: str,
    group_index: int = 0,
    x_axis_index: int = 1,
    y_axis_index: int = 2,
    output_file: str | None = None,
    figsize: tuple[int, int] = (12, 5),
    log_y: bool = False,
) -> None:
    """Plot grouped metric series from tabular benchmark results."""
    grouped_values: dict[str, list[tuple[float, float]]] = defaultdict(list)
    x_tick_set = set()

    for row in data:
        group = str(row[group_index])
        x_value = float(row[x_axis_index])
        y_value = float(row[y_axis_index])

        grouped_values[group].append((x_value, y_value))
        x_tick_set.add(x_value)

    plt.figure(figsize=figsize)

    primary_labels = {_split_group_label(group)[0] for group in grouped_values}
    colors = _assign_colors(sorted(primary_labels))

    for group in sorted(grouped_values):
        values = grouped_values[group]
        values.sort()
        x_values, y_values = zip(*values)
        primary, remainder = _split_group_label(group)
        linestyle = _LINESTYLES[_stable_hash(remainder) % len(_LINESTYLES)] if remainder else "-"
        marker = _MARKERS[_stable_hash(remainder) % len(_MARKERS)] if remainder else "o"
        plt.plot(
            x_values,
            y_values,
            marker=marker,
            linestyle=linestyle,
            color=colors[primary],
            label=group,
        )

    if grouped_values:
        plt.legend()

    finish_plot(
        x_axis_label,
        y_axis_label,
        title,
        sorted(x_tick_set),
        output_file,
        log_y=log_y,
    )


def parse_args(argv=None):
    """
    Parse command-line arguments for the provenance processing script.

    Returns:
        argparse.Namespace: Parsed arguments containing:
            - benchmark_name: Benchmark name used in RoHub annotations
            - tool: Optional tool name used to filter plotted data
            - output_file: Path for the final visualization output
            - x_axis_label: Label for the x-axis
            - y_axis_label: Label for the y-axis
            - plot_title: Title for the plot
            - parameters: Parameter names to query
            - metrics: Metric names to query
    """
    parser = argparse.ArgumentParser(
        description="Fetch benchmark provenance from RoHub and plot simulation metrics."
    )
    parser.add_argument(
        "--output-file",
        dest="output_file",
        type=str,
        default=None,
        required=False,
        help="Final visualization file. When omitted, the plot is displayed.",
    )
    parser.add_argument(
        "--x-axis-label",
        type=str,
        default="X Axis Label",
        help="Label for the x-axis.",
    )
    parser.add_argument(
        "--y-axis-label",
        type=str,
        default="Y Axis Label",
        help="Label for the y-axis.",
    )
    parser.add_argument(
        "--plot-title",
        type=str,
        default="Plot Title",
        help="Title for the plot.",
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
        "--code-repository-url",
        type=str,
        default=None,
        help="Optional Git branch URL used to filter RoHub results.",
    )
    parser.add_argument(
        "--use-production-rohub",
        action="store_true",
        default=False,
        help="Use production RoHub instead of the development instance.",
    )
    parser.add_argument(
        "--parameters",
        nargs="+",
        default=None,
        help="Parameter names to query from RoHub.",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=None,
        help="Metric names to query from RoHub.",
    )
    parser.add_argument(
        "--log-y",
        action="store_true",
        default=False,
        help="Use a logarithmic scale for the y-axis.",
    )
    return parser.parse_args(argv)


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
    return load_benchmark_metric_data(
        benchmark_name=args.benchmark_name,
        parameters=parameters,
        metrics=metrics,
        tool=args.tool,
        code_repository_url=args.code_repository_url,
        use_production_rohub=args.use_production_rohub,
    )


def select_plot_columns(
    data: pd.DataFrame,
    parameters: Sequence[str],
    metrics: Sequence[str],
    group_column: str = "tool_name",
) -> pd.DataFrame:
    """Select the group, x-axis, and y-axis columns used for plotting.

    Parameters beyond the first are folded into the group label so that
    runs differing only in a secondary parameter become distinct series.
    """
    if not parameters:
        raise ValueError("At least one parameter is required for the x-axis.")
    if not metrics:
        raise ValueError("At least one metric is required for the y-axis.")

    extra_params = list(parameters[1:])
    required_columns = [group_column, parameters[0], metrics[0]] + extra_params
    missing_columns = [col for col in required_columns if col not in data.columns]

    if missing_columns:
        raise ValueError(
            "Cannot plot because these columns are missing: "
            + ", ".join(missing_columns)
        )

    df = data.loc[:, required_columns].copy()
    if extra_params:
        df[group_column] = df.apply(
            lambda row: ", ".join(
                [str(row[group_column])]
                + [f"{p}={row[p]}" for p in extra_params]
            ),
            axis=1,
        )

    return df.loc[:, [group_column, parameters[0], metrics[0]]].reset_index(drop=True)


def plot_results(final_df: pd.DataFrame, args) -> None:
    """
    Generate a visualization plot of the provenance results.

    Creates a scatter/line plot showing the relationship between element size
    and maximum von Mises stress.

    Args:
        final_df (pd.DataFrame): DataFrame containing filtered data to plot.
                                Expected columns: element_size,
                                max_von_mises_stress (in that order).
        args (argparse.Namespace): Plot configuration arguments.
    """

    plot_provenance_graph(
        data=final_df.values.tolist(),
        x_axis_label=args.x_axis_label,
        y_axis_label=args.y_axis_label,
        group_index=0,
        x_axis_index=1,
        y_axis_index=2,
        title=args.plot_title,
        output_file=args.output_file,
        log_y=args.log_y,
    )


def run(
    args,
    parameters: Sequence[str],
    metrics: Sequence[str],
    prepare_data: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
) -> None:
    """
    Execute the complete provenance analysis workflow.

    Performs the following steps:
    1. Fetch benchmark provenance from RoHub
    2. Select the configured parameter/metric columns
    3. Generate visualization plot

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        parameters (list): List of parameter names to extract.
        metrics (list): List of metric names to extract.
        prepare_data: Optional hook for benchmark-specific data filtering.
    """
    provenance_df = load_and_query_rohub(args, parameters, metrics)
    if prepare_data is not None:
        provenance_df = prepare_data(provenance_df)

    final_df = select_plot_columns(
        provenance_df,
        parameters,
        metrics,
    )

    plot_results(final_df, args)


def main():
    """
    Main entry point for the provenance analysis script.

    Parses command-line arguments and executes the analysis workflow.
    """
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    args = parse_args()

    if args.parameters is None or args.metrics is None:
        raise ValueError(
            "When running plot_metrics.py directly, provide --parameters and --metrics."
        )

    run(args, args.parameters, args.metrics)


if __name__ == "__main__":
    main()
