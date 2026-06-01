"""Run the Kratos benchmark for each semantic benchmark configuration.

The script performs the following steps:

1. Extracts the benchmark workflow files from a user-provided zip archive.
2. Loads the semantic benchmark JSON-LD file and writes one parameter JSON file
   per benchmark configuration.
3. Creates a per-configuration result directory.
4. Runs the Snakemake workflow once normally and once with the provenance
   reporter enabled.
5. Creates an aggregate RO-Crate from all configuration results.
"""

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "provenance"))
import semantic_benchmark
import create_rocrate

ROOT_UNZIPPED_BENCHMARK_DIR = Path(__file__).resolve().parent
PROVENANCE_REPORTER_NAME = "metadata4ing"
PROVENANCE_REPORT_NAME = "NFDI4Ing Provenance"
PROVENANCE_REPORT_DESCRIPTION = "Benchmark for linear-elastic plate with a hole"
PROVENANCE_REPORT_LICENSE = "https://opensource.org/licenses/MIT"
PROVENANCE_REPORT_PROFILE = "provenance-run-crate-0.5"
DEFAULT_ROCRATE_FILENAME = "Kratos-RoCrate.zip"
DEFAULT_SOFTWARE_NAME = "Kratos"
SNAKEMAKE_FILE_NAME = "Snakefile.smk"

UNIT_SYMBOLS = {
    "unit:M": "m",
    "unit:PA": "Pa",
    "unit:N": "N",
}


def parse_arguments() -> Namespace:
    """Parse command-line arguments for the Kratos benchmark runner."""
    parser = argparse.ArgumentParser(
        description="Run the Kratos benchmark workflow for all benchmark configurations."
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
        "--rocrate-filename",
        type=Path,
        default=DEFAULT_ROCRATE_FILENAME,
        help="Filename or path for the generated aggregate RO-Crate zip file.",
    )
    parser.add_argument(
        "--software-name",
        default=DEFAULT_SOFTWARE_NAME,
        help="Software name recorded in the generated aggregate RO-Crate.",
    )
    return parser.parse_args()


def extract_benchmark_archive(benchmark_zip: Path, output_dir: Path) -> None:
    """Extract the zipped benchmark workflow into the Kratos working directory.

    Args:
        benchmark_zip: Path to the benchmark zip archive.
        output_dir: Directory where the archive contents will be extracted.
    """
    with zipfile.ZipFile(benchmark_zip.expanduser().resolve(), "r") as zip_ref:
        zip_ref.extractall(output_dir)


def create_shared_conda_env_dir(benchmark_dir: Path) -> Path:
    """Create and return the shared Snakemake conda environment directory.

    Snakemake receives this path for every configuration so environments can be
    reused instead of recreated for each benchmark run.
    """
    shared_env_dir = benchmark_dir / "conda_envs"
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
    """Copy benchmark workflow files into a configuration result directory.

    Generated parameter files are excluded because the selected configuration is
    already copied as parameters.json.
    """
    for item in benchmark_dir.iterdir():
        if not item.is_file():
            continue

        if item.name.startswith("parameters_") and item.suffix == ".json":
            continue

        shutil.copy(item, output_dir / item.name)


def build_snakemake_command(parameter_file: Path, shared_env_dir: Path) -> list[str]:
    """Build the base Snakemake command for one configuration."""
    return [
        "snakemake",
        "--snakefile",
        SNAKEMAKE_FILE_NAME,
        "--use-conda",
        "--force",
        "--cores",
        "all",
        "--conda-prefix",
        str(shared_env_dir),
        "--configfile",
        str(parameter_file),
    ]


def build_provenance_reporter_args(configuration: str) -> list[str]:
    """Build Snakemake reporter arguments for the metadata4ing provenance crate."""
    return [
        "--reporter",
        PROVENANCE_REPORTER_NAME,
        "--report-metadata4ing-filename",
        f"Kratos-{configuration}",
        "--report-metadata4ing-name",
        PROVENANCE_REPORT_NAME,
        "--report-metadata4ing-description",
        PROVENANCE_REPORT_DESCRIPTION,
        "--report-metadata4ing-license",
        PROVENANCE_REPORT_LICENSE,
        "--report-metadata4ing-profile",
        PROVENANCE_REPORT_PROFILE,
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
    run_snakemake_workflow(parameter_file, configuration, output_dir, shared_env_dir)

    print(f"Workflow executed successfully for configuration {configuration}.")


def create_aggregate_rocrate(
    results_dir: Path,
    benchmark: semantic_benchmark.SemanticBenchmark,
    rocrate_filename: Path,
    software_name: str,
) -> None:
    """Create one aggregate RO-Crate from all per-configuration result crates."""
    create_rocrate.create_main_ro(
        str(results_dir),
        benchmark,
        rocrate_filename=str(rocrate_filename),
        software_name=software_name,
    )
    print(f"Aggregate RO-Crate created at {rocrate_filename}.")


def resolve_rocrate_filename(rocrate_filename: Path, benchmark_dir: Path) -> Path:
    """Resolve relative aggregate RO-Crate filenames inside the benchmark directory."""
    output_path = rocrate_filename.expanduser()
    if output_path.is_absolute():
        return output_path
    return benchmark_dir / output_path


def run_benchmark(args: Namespace) -> None:
    """Run the complete Kratos benchmark workflow from parsed arguments."""
    benchmark_dir = ROOT_UNZIPPED_BENCHMARK_DIR

    extract_benchmark_archive(args.benchmark_zip, benchmark_dir)
    shared_env_dir = create_shared_conda_env_dir(benchmark_dir)

    benchmark = load_benchmark(args.benchmark_file)
    create_parameter_files_from_benchmark(benchmark, benchmark_dir)

    for parameter_file in sorted(benchmark_dir.glob("parameters_*.json")):
        run_configuration(parameter_file, benchmark_dir, shared_env_dir)

    create_aggregate_rocrate(
        benchmark_dir / "results",
        benchmark,
        rocrate_filename=resolve_rocrate_filename(args.rocrate_filename, benchmark_dir),
        software_name=args.software_name,
    )


def main() -> None:
    """Parse arguments and run the Kratos benchmark."""
    args = parse_arguments()
    run_benchmark(args)


if __name__ == "__main__":
    main()
