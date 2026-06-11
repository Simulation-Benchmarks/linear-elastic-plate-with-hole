"""Run the Fenics benchmark for each semantic benchmark configuration."""

import argparse
import json
import logging
import shutil
import subprocess
import sys
import zipfile
from argparse import Namespace
from pathlib import Path

# Monkey-patch pulp for compatibility with newer versions
try:
    import pulp
    if not hasattr(pulp, 'list_solvers') and hasattr(pulp, 'listSolvers'):
        pulp.list_solvers = pulp.listSolvers
except ImportError:
    pass

from rocrate_validator import models, services

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVENANCE_DIR = REPO_ROOT / "provenance"
if str(PROVENANCE_DIR) not in sys.path:
    sys.path.insert(0, str(PROVENANCE_DIR))

import create_rocrate
import semantic_benchmark

LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"
LOGGER = logging.getLogger(__name__)

TOOL_NAME = "Fenics"
BENCHMARK_DIR = Path(__file__).resolve().parent

PROVENANCE_REPORTER_NAME = "metadata4ing"
PROVENANCE_REPORT_NAME = "NFDI4Ing Provenance"
PROVENANCE_REPORT_DESCRIPTION = "Benchmark for linear-elastic plate with a hole"
PROVENANCE_REPORT_LICENSE = "https://opensource.org/licenses/MIT"
PROVENANCE_PROFILE = "provenance-run-crate-0.5"

UNIT_SYMBOLS = {
    "unit:M": "m",
    "unit:PA": "Pa",
}


def configure_logging() -> None:
    """Configure default logging for command-line benchmark runs."""
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def build_default_rocrate_name() -> str:
    """Build the default aggregate RO-Crate filename."""
    return f"{TOOL_NAME}-RoCrate.zip"


def parse_arguments() -> Namespace:
    """Parse command-line arguments for the Fenics benchmark runner."""
    parser = argparse.ArgumentParser(
        description=(
            f"Run the {TOOL_NAME} benchmark workflow for all benchmark "
            "configurations."
        )
    )
    parser.add_argument(
        "--benchmark-file",
        type=Path,
        required=True,
        help="Path to the semantic benchmark JSON-LD file.",
    )
    parser.add_argument(
        "--benchmark-zip",
        type=Path,
        required=True,
        help="Path to the zipped benchmark archive to extract.",
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
        default=build_default_rocrate_name(),
        help="Filename or path for the generated aggregate RO-Crate zip file.",
    )
    parser.add_argument(
        "--software-name",
        default=TOOL_NAME,
        help="Software name recorded in the generated aggregate RO-Crate.",
    )
    return parser.parse_args()


def extract_benchmark_archive(benchmark_zip: Path, output_dir: Path) -> None:
    """Extract the zipped benchmark workflow into the tool working directory."""
    with zipfile.ZipFile(benchmark_zip.expanduser().resolve(), "r") as zip_ref:
        zip_ref.extractall(output_dir)


def create_shared_conda_env_dir(benchmark_dir: Path) -> Path:
    """Create and return the shared Snakemake conda environment directory."""
    shared_env_dir = benchmark_dir / "conda_envs"
    if shared_env_dir.exists():
        shutil.rmtree(shared_env_dir)
    shared_env_dir.mkdir(parents=True, exist_ok=True)
    return shared_env_dir


def parameter_json_key(parameter) -> str:
    """Build the parameters.json key, including the unit suffix when present."""
    unit_symbol = UNIT_SYMBOLS.get(parameter.unit)
    if unit_symbol:
        return f"{parameter.label}[{unit_symbol}]"
    return parameter.label


def parameter_json_value(parameter):
    """Extract the scalar value stored in a benchmark parameter object."""
    if isinstance(parameter, semantic_benchmark.TextParameter):
        return parameter.string_value
    return getattr(parameter, "numerical_value", None)


def load_benchmark(benchmark_file: Path) -> semantic_benchmark.SemanticBenchmark:
    """Load the semantic benchmark description from a JSON-LD file."""
    return semantic_benchmark.BenchmarkLoader(benchmark_file).load()


def create_parameter_files_from_benchmark(
    benchmark: semantic_benchmark.SemanticBenchmark,
    output_dir: Path,
) -> None:
    """Create parameters_*.json files from the benchmark configuration objects."""
    for stale_file in output_dir.glob("parameters_*.json"):
        stale_file.unlink()

    for configuration in benchmark.parameter_sets:
        if not configuration.identifier:
            continue

        payload = {"configuration": configuration.identifier}
        for parameter in configuration.parts:
            payload[parameter_json_key(parameter)] = parameter_json_value(parameter)

        parameter_file = output_dir / f"parameters_{configuration.identifier}.json"
        with open(parameter_file, "w") as outfile:
            json.dump(payload, outfile, indent=4)
            outfile.write("\n")


def load_parameter_file(parameter_file: Path) -> dict:
    """Load a generated parameter JSON file."""
    with open(parameter_file, "r") as infile:
        return json.load(infile)


def create_configuration_output_dir(benchmark_dir: Path, configuration: str) -> Path:
    """Create and return the result directory for a benchmark configuration."""
    output_dir = benchmark_dir / "results" / configuration
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def create_parameter_file(configuration_data: dict, output_dir: Path) -> None:
    """Write the selected configuration as parameters.json in the result directory."""
    with open(output_dir / "parameters.json", "w") as outfile:
        json.dump(configuration_data, outfile, indent=2)


def copy_benchmark_files_to_output_dir(benchmark_dir: Path, output_dir: Path) -> None:
    """Copy benchmark workflow files into a configuration result directory."""
    for item in benchmark_dir.iterdir():
        if not item.is_file():
            continue

        if item.name.startswith("parameters_") and item.suffix == ".json":
            continue

        shutil.copy(item, output_dir / item.name)


def build_snakemake_command(
    parameter_file: Path,
    shared_env_dir: Path,
) -> list[str]:
    """Build the base Snakemake command for one configuration."""
    return [
        "snakemake",
        "--use-conda",
        "--force",
        "--cores",
        "all",
        "--conda-prefix",
        str(shared_env_dir),
        "--configfile",
        str(parameter_file),
        "--conda-cleanup-pkgs",
        "none",
    ]


def build_provenance_reporter_args(configuration: str) -> list[str]:
    """Build Snakemake reporter arguments for the metadata4ing provenance crate."""
    return [
        "--reporter",
        PROVENANCE_REPORTER_NAME,
        "--report-metadata4ing-filename",
        f"{TOOL_NAME}-{configuration}",
        "--report-metadata4ing-name",
        PROVENANCE_REPORT_NAME,
        "--report-metadata4ing-description",
        PROVENANCE_REPORT_DESCRIPTION,
        "--report-metadata4ing-license",
        PROVENANCE_REPORT_LICENSE,
        "--report-metadata4ing-profile",
        PROVENANCE_PROFILE,
    ]


def run_snakemake_workflow(
    parameter_file: Path,
    configuration: str,
    output_dir: Path,
    shared_env_dir: Path,
) -> None:
    """Run the Snakemake workflow normally and then with provenance reporting."""
    base_cmd = build_snakemake_command(parameter_file, shared_env_dir)
    reporter_args = build_provenance_reporter_args(configuration)

    subprocess.run(base_cmd, check=True, cwd=output_dir)
    subprocess.run(base_cmd + reporter_args, check=True, cwd=output_dir)


def run_configuration(
    parameter_file: Path,
    benchmark_dir: Path,
    shared_env_dir: Path,
) -> None:
    """Prepare and execute one benchmark configuration."""
    configuration_data = load_parameter_file(parameter_file)
    configuration = configuration_data.get("configuration")
    if not configuration:
        raise ValueError(f"Missing configuration value in {parameter_file}")

    output_dir = create_configuration_output_dir(benchmark_dir, configuration)

    create_parameter_file(configuration_data, output_dir)
    copy_benchmark_files_to_output_dir(benchmark_dir, output_dir)
    run_snakemake_workflow(
        parameter_file,
        configuration,
        output_dir,
        shared_env_dir,
    )

    LOGGER.info("Workflow executed successfully for configuration %s.", configuration)


def create_aggregate_rocrate(
    results_dir: Path,
    benchmark: semantic_benchmark.SemanticBenchmark,
    rocrate_path: Path,
    software_name: str,
) -> None:
    """Create one aggregate RO-Crate from all per-configuration result crates."""
    create_rocrate.create_main_ro(
        str(results_dir),
        benchmark,
        rocrate_path=str(rocrate_path),
        software_name=software_name,
    )
    LOGGER.info("Aggregate RO-Crate created at %s.", rocrate_path)


def validate_rocrate(rocrate_path: str, profile: str = PROVENANCE_PROFILE) -> None:
    """Validate the RO-Crate folder against the specified profile."""
    settings = services.ValidationSettings(
        rocrate_uri=rocrate_path,
        profile_identifier=profile,
        requirement_severity=models.Severity.REQUIRED,
    )
    result = services.validate(settings)
    assert not result.has_issues(), "RO-Crate is invalid!\n" + "\n".join(
        f"Detected issue of severity {issue.severity.name} with check "
        f'"{issue.check.identifier}": {issue.message}'
        for issue in result.get_issues()
    )
    LOGGER.info("RO-Crate is valid.")


def run_benchmark(args: Namespace) -> None:
    """Run a complete Fenics benchmark workflow from parsed arguments."""
    configure_logging()

    extract_benchmark_archive(args.benchmark_zip, BENCHMARK_DIR)
    shared_env_dir = create_shared_conda_env_dir(BENCHMARK_DIR)

    benchmark = load_benchmark(args.benchmark_file)
    create_parameter_files_from_benchmark(benchmark, BENCHMARK_DIR)

    for parameter_file in sorted(BENCHMARK_DIR.glob("parameters_*.json")):
        run_configuration(parameter_file, BENCHMARK_DIR, shared_env_dir)

    create_aggregate_rocrate(
        args.result_path,
        benchmark,
        rocrate_path=args.result_path / args.rocrate_name,
        software_name=args.software_name,
    )

    with zipfile.ZipFile(args.result_path / args.rocrate_name, "r") as zip_ref:
        zip_ref.extractall(args.result_path / "unpacked_rocrate")

    validate_rocrate(
        rocrate_path=str(args.result_path / "unpacked_rocrate"),
        profile=PROVENANCE_PROFILE,
    )


def main() -> None:
    """Parse arguments and run the Fenics benchmark."""
    configure_logging()
    run_benchmark(parse_arguments())


if __name__ == "__main__":
    main()
