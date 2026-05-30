from pathlib import Path
import argparse
import zipfile
import json
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "provenance"))
import semantic_benchmark


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmark-file",
        type=Path,
        required=True,
        help="Path to the semantic benchmark JSON-LD file.",
    )
    return parser.parse_args()


args = parse_arguments()

"""
The script performs the following steps:

1. Extracts the benchmark files from a zip archive (currently assuming that it is an RO-Crate of the benchmark).
2. Iterates through the parameter configuration files, checks the "element-size" value, and if it meets the specified condition (>= 0.025)
, it executes the Snakemake workflow for that configuration.

The results of each run (and the files used by it) are stored in the directory with the configuration name.
"""

####################################################################################################
####################################################################################################
# Benchmark Extraction
####################################################################################################
####################################################################################################

root_zipped_benchmark_dir = Path(__file__).resolve().parent.parent
root_unzipped_benchmark_dir = Path(__file__).resolve().parent

with zipfile.ZipFile(root_zipped_benchmark_dir / "benchmark/linear-elastic-plate-with-hole.zip", 'r') as zip_ref:
    # Extract all files
    zip_ref.extractall(root_unzipped_benchmark_dir)
    
    
#Creates a directory to store the conda environments. The environments are shared across different parameter configurations.
#To avoid redundant creation of environments, this path will be passed to all snakemake files during execution.
        
shared_env_dir = root_unzipped_benchmark_dir / "conda_envs"
shared_env_dir.mkdir(parents=True, exist_ok=True)  

####################################################################################################
####################################################################################################
# Simulation tool metadata (to be included in the RO-Crate)
####################################################################################################
####################################################################################################

tool_name = "fenics"
tool_uri =  "https://github.com/FEniCS/dolfinx"
tool_version = "0.9.0"

####################################################################################################
####################################################################################################
# Conditional execution of parameter configurations 
####################################################################################################
####################################################################################################

UNIT_SYMBOLS = {
    "unit:M": "m",
    "unit:PA": "Pa",
}


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


def write_parameter_files_from_benchmark(
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


benchmark_object = semantic_benchmark.BenchmarkLoader(args.benchmark_file).load()
write_parameter_files_from_benchmark(benchmark_object, root_unzipped_benchmark_dir)

for file in sorted(root_unzipped_benchmark_dir.glob("parameters_*.json")):
    with open(file, "r") as f:
        data = json.load(f)


        # Create output directory for the configuration
        output_dir = root_unzipped_benchmark_dir / "results" / data.get("configuration")
        output_dir.mkdir(parents=True, exist_ok=True) 
            
        # Copy the selected parameter file to the output directory with a standardised name
        with open(output_dir / "parameters.json", "w") as outfile:
            json.dump(data, outfile, indent=2)

        # Copy files from benchmark_dir to output_dir, excluding non-matching parameter files.
        for item in root_unzipped_benchmark_dir.iterdir():
            if item.is_file():
                if item.name.startswith("parameters_") and item.suffix == ".json":
                    continue
                else:
                    shutil.copy(item, output_dir / item.name)
        
        base_cmd = [
            "snakemake",
            "--use-conda",
            "--force",
            "--cores", "all",
            "--conda-prefix", str(shared_env_dir),
            "--configfile", str(file),
        ]
        
        reporter_args = [
            "--reporter", "metadata4ing",
            "--report-metadata4ing-filename", f"Fenics-{data.get('configuration')}",
            "--report-metadata4ing-name", "NFDI4Ing Provenance",
            "--report-metadata4ing-description", "Benchmark for linear-elastic plate with a hole",
            "--report-metadata4ing-license", "https://opensource.org/licenses/MIT",
            "--report-metadata4ing-profile", "provenance-run-crate-0.5",
        ]
        
        # Run the Snakemake workflow from the benchmark to create the mesh for the configuration
        subprocess.run(
            base_cmd,
            check=True,
            cwd=output_dir,
        )
        
        # Second run: with provenance reporter
        subprocess.run(
            base_cmd + reporter_args,
            check=True,
            cwd=output_dir,
        )
        
        print("Workflow executed successfully.")
            
        # For the scenario where the snakemake workflow doesn't exist, one can directly run the simulation script using the subprocess module, e.g.:
        #subprocess.run(["python", "run_fenics_simulation.py" \
                        #"--input_parameter_file" str(file) \
                        #"--input_mesh_file" "mesh.msh" \
                        #"--output_solution_file_zip" "solution_field_data.zip" \
                        #"--output_metrics_file" "solution_metrics.json"], check=True, cwd=output_dir)
                        
        #Assuming the mesh.msh and parameters.json files are present/copied to the output_dir.
