"""Run the EdelweissFE benchmark for each semantic benchmark configuration."""

import argparse
import json
import logging
import subprocess
from argparse import Namespace
from pathlib import Path

from semantic_benchmark import runner

LOGGER = logging.getLogger(__name__)

BENCHMARK_DIR = Path(__file__).resolve().parent

UNIT_SYMBOLS = {
    "M": "m",
    "METRE": "m",
    "METER": "m",
    "PA": "Pa",
    "PASCAL": "Pa",
}


def parse_arguments() -> Namespace:
    """Parse command-line arguments for the EdelweissFE benchmark runner."""
    parser = argparse.ArgumentParser(
        description="Run the benchmark workflow for all benchmark configurations."
    )
    parser.add_argument(
        "--benchmark-file",
        type=Path,
        required=True,
        help="Path to the semantic benchmark JSON-LD file.",
    )
    parser.add_argument(
        "--result-path",
        type=Path,
        required=True,
        help="Path for benchmark results",
    )
    parser.add_argument(
        "--rocrate-name",
        type=str,
        default=None,
        help="Filename or path for the generated aggregate RO-Crate zip file.",
    )
    parser.add_argument(
        "--aggregated-profile",
        type=Path,
        default=BENCHMARK_DIR.parent / "provenance" / "profiles" / "aggregate-rocrate-edelweissFE.yml",
        help="Aggregate RO-Crate profile YAML file.",
    )
    parser.add_argument(
        "--subcrate-profile",
        type=Path,
        required=True,
        help="Path to the subcrate RO-Crate profile YAML file.",
    )
    parser.add_argument(
        "--workflow-path",
        type=Path,
        required=True,
        help="YAML workflow file used as the aggregate crate main entity.",
    )
    return parser.parse_args()


def build_snakemake_command(
    parameter_file: Path,
    shared_env_dir_conda: Path,
    shared_env_dir_apptainer: Path,
    software_version: str,
) -> list[str]:
    """Build the base Snakemake command for one configuration."""
    return [
        "snakemake",
        "--use-conda",
        "--use-apptainer",
        "--force",
        "--cores",
        "all",
        "--conda-prefix",
        str(shared_env_dir_conda),
        "--apptainer-prefix",
        str(shared_env_dir_apptainer),
        "--configfile",
        str(parameter_file),
        "--config",
        f"software_version={software_version}",
    ]


def run_snakemake_workflow(
    parameter_file: Path,
    output_dir: Path,
    shared_env_dir_conda: Path,
    shared_env_dir_apptainer: Path,
    software_version: str,
    subcrate_profile: Path,
) -> None:
    """Run the Snakemake workflow normally and then with provenance reporting."""
    base_cmd = build_snakemake_command(
        parameter_file,
        shared_env_dir_conda,
        shared_env_dir_apptainer,
        software_version,
    )
    reporter_args = runner.build_subcrate_args(subcrate_profile)

    subprocess.run(base_cmd, check=True, cwd=output_dir)
    subprocess.run(base_cmd + reporter_args, check=True, cwd=output_dir)


def run_configuration(
    parameter_file: Path,
    benchmark_dir: Path,
    shared_env_dir_conda: Path,
    shared_env_dir_apptainer: Path,
    software_version: str,
    subcrate_profile: Path,
) -> Path:
    """Prepare and execute one benchmark configuration."""
    configuration, output_dir = runner.prepare_configuration(
        parameter_file, benchmark_dir
    )
    run_snakemake_workflow(
        output_dir / "parameters.json",
        output_dir,
        shared_env_dir_conda,
        shared_env_dir_apptainer,
        software_version,
        subcrate_profile,
    )

    LOGGER.info("Workflow executed successfully for configuration %s.", configuration)
    return runner.reporter_rocrate_path(output_dir)


def run_benchmark(args: Namespace) -> None:
    """Run a complete EdelweissFE benchmark workflow from parsed arguments."""
    benchmark = runner.prepare_benchmark(
        args.benchmark_file,
        BENCHMARK_DIR,
        UNIT_SYMBOLS,
        resource_dir=args.benchmark_file.parent,
        shared_directories=("conda_envs", "apptainer_envs"),
        strict_units=True,
        aggregate_profile=args.aggregated_profile,
    )
    aggregate_metadata = benchmark.aggregate_profile
    shared_env_dir_conda = BENCHMARK_DIR / "conda_envs"
    shared_env_dir_apptainer = BENCHMARK_DIR / "apptainer_envs"
    subcrate_paths = []

    for parameter_file in sorted(BENCHMARK_DIR.glob("parameters_*.json")):
        with open(parameter_file) as f:
            parameters = json.load(f)

        # EdelweissFE has no triangular plane element, so only the
        # quadrilateral configurations of the benchmark can be run.
        cell_type = parameters.get("cell_type")
        if cell_type == "quadrilateral":
            subcrate_paths.append(
                run_configuration(
                    parameter_file,
                    BENCHMARK_DIR,
                    shared_env_dir_conda,
                    shared_env_dir_apptainer,
                    aggregate_metadata.software_version,
                    args.subcrate_profile,
                )
            )
        else:
            LOGGER.info(
                "Skipping configuration %s with cell_type '%s'.",
                parameters["configuration"],
                cell_type,
            )

    rocrate_name = args.rocrate_name or f'{aggregate_metadata.software_name}-RoCrate.zip'
    rocrate_path = args.result_path / rocrate_name
    runner.create_aggregate_rocrate(
        args.result_path,
        benchmark,
        rocrate_path,
        subcrate_paths=subcrate_paths,
        workflow_path=args.workflow_path,
    )
    LOGGER.info("Aggregate RO-Crate created at %s.", rocrate_path)


def main() -> None:
    """Parse arguments and run the EdelweissFE benchmark."""
    runner.configure_logging()
    run_benchmark(parse_arguments())


if __name__ == "__main__":
    main()
