"""Run the Fenics benchmark for each semantic benchmark configuration."""

import sys
from argparse import Namespace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark_runner.common import (
    BenchmarkRunnerConfig,
    parse_arguments,
    run_benchmark as run_configured_benchmark,
)

CONFIG = BenchmarkRunnerConfig(
    tool_name="Fenics",
    benchmark_dir=Path(__file__).resolve().parent,
)


def run_benchmark(args: Namespace) -> None:
    """Run the Fenics benchmark using the shared benchmark runner."""
    run_configured_benchmark(args, CONFIG)


def main() -> None:
    """Parse arguments and run the Fenics benchmark."""
    run_benchmark(parse_arguments(CONFIG))


if __name__ == "__main__":
    main()
