# Infinite Plate with Hole Benchmark

A benchmark for the linear elastic infinite plate with a hole problem, solved using various finite-element simulation tools.

## Problem Definition

See the [documentation](docs/plate-with-hole.md) for a detailed problem definition and mathematical formulation.

## Repository Structure

```
.
├── docs/                          # Benchmark documentation
├── common/                          # Shared postprocessing & provenance scripts
├── fenics/                          # FEniCS implementation
├── kratos/                          # Kratos Multiphysics implementation
├── extendablefem/                   # ExtendableFEM.jl implementation
├── notebooks/                       # Jupyter notebooks for exploring results
├── tests/                           # Test reference data
├── create_mesh.py                   # Mesh generation script
├── generate_config.py               # Workflow configuration generator
├── plot_metrics.py                  # Post-processing & plotting script
├── Snakefile                        # Snakemake workflow
├── main.nf                          # Nextflow workflow
└── parameters_*.json                # Parameter configurations
```

## Running the Benchmark

1. **Generate Configuration Files**

   ```bash
   python generate_config.py
   ```

   This creates `workflow_config.json` that defines what configurations are computed and what tools are used.

2. **Run the Benchmark**

   Via Snakemake:
   ```bash
   snakemake --use-conda --cores all
   ```

   Or via Nextflow:
   ```bash
   nextflow run main.nf -params-file workflow_config.json -c common/nextflow.config -plugins nf-prov@1.4.0
   ```

3. **Collect Provenance**

   ```bash
   snakemake --use-conda --cores all --reporter metadata4ing
   ```

   Output and provenance files are stored in the `snakemake_results/` directory.

## Adding a New Simulation Tool

1. Create a new subdirectory for the tool.
2. Create a new `Snakefile` with at least one rule that produces the required outputs (metrics and solution fields).
3. Ensure the rule accepts the standardized parameter file and mesh/input files.
4. Update the main `Snakefile` and `main.nf` to include the new tool's rules.

## Acknowledgments

This benchmark was originally developed as part of the [NFDI4Ing Model Validation Platform](https://github.com/BAMresearch/NFDI4IngModelValidationPlatform).
