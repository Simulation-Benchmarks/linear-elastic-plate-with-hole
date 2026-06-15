import argparse
import logging

import pandas as pd

from plot_metrics import parse_args, run
from utils import parse_bool

LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"

BENCHMARK_NAME = "linear-elastic-plate-with-hole"
PARAMETERS = ["element_size", "isoparametric_element_degree"]
METRICS = ["max_von_mises_stress"]
X_AXIS_LABEL = "Element Size"
Y_AXIS_LABEL = "Max Von Mises Stress"
PLOT_TITLE = "Element Size vs Max Von Mises Stress"
OUTPUT_FILE_TEMPLATE = "{tool}-element-size-vs-stress-plot.pdf"

def parse_workflow_args(argv=None):
    """Parse only the arguments that vary in the benchmark workflow."""
    parser = argparse.ArgumentParser(
        description="Plot the plate-with-hole benchmark stress metric from RoHub."
    )
    parser.add_argument(
        "--tool",
        type=str,
        required=True,
        help="Tool name used to filter RoHub results",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Final visualization file.",
    )
    parser.add_argument(
        "--use-production-rohub",
        type=parse_bool,
        default=False,
        help="Use production RoHub instead of the development instance (true/false).",
    )
    return parser.parse_args(argv)


def build_plot_args(args):
    """Build the full argument namespace expected by plot_metrics.run."""
    return parse_args(
        [
            "--benchmark-name",
            BENCHMARK_NAME,
            "--parameters",
            *PARAMETERS,
            "--metrics",
            *METRICS,
            "--tool",
            args.tool,
            "--x-axis-label",
            X_AXIS_LABEL,
            "--y-axis-label",
            Y_AXIS_LABEL,
            "--plot-title",
            f"{PLOT_TITLE} ({args.tool})",
            "--output-file",
            args.output_file or OUTPUT_FILE_TEMPLATE.format(tool=args.tool),
            "--use-production-rohub",
            str(args.use_production_rohub).lower(),
        ]
    )


def keep_first_order_linear_elements(data: pd.DataFrame) -> pd.DataFrame:
    """Keep only first-order linear elements for this benchmark plot."""
    return (
        data.query("isoparametric_element_degree == '1'")
        .reset_index(drop=True)
    )


def main():
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    args = build_plot_args(parse_workflow_args())

    run(
        args,
        PARAMETERS,
        METRICS,
        prepare_data=keep_first_order_linear_elements,
    )


if __name__ == "__main__":
    main()
