# Infinite Plate with Hole Benchmark

[![REUSE status](https://api.reuse.software/badge/github.com/Simulation-Benchmarks/linear-elastic-plate-with-hole)](https://api.reuse.software/info/github.com/Simulation-Benchmarks/linear-elastic-plate-with-hole)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21718397.svg)](https://doi.org/10.5281/zenodo.21718397)

A benchmark for the linear-elastic infinite plate with a circular hole, solved with several finite-element simulation tools and evaluated against the analytical Kirsch solution.

## Problem Description

An infinite plate with a circular hole of radius $a$ is subjected to uniform tensile load $p$ at infinity. The analytical stress field (Kirsch, 1898) is used to set Dirichlet and Neumann boundary conditions on a finite quarter-domain, making the full analytical solution available for error evaluation.

Metrics reported for each run:
- **Max von Mises stress** — convergence towards the stress-concentration peak at the hole boundary
- **Max displacement error** — pointwise maximum of the displacement error against the analytical solution
- **L2 displacement error** — L2 norm of the displacement error over the domain

See [documentation](docs/benchmark-documentation.md) for the full mathematical formulation.

## Simulation Tools

Implementations are provided for three FE frameworks, each with its own subdirectory and Snakemake workflow:

| Tool | Directory | Language |
|------|-----------|----------|
| [FEniCS](https://fenicsproject.org) | `fenics/` | Python |
| [ExtendableFEM.jl](https://github.com/WIAS-PDELib/ExtendableFEM.jl) | `extendablefem/` | Julia |
| [KratosMultiphysics](https://kratosmultiphysics.github.io) | `kratos/` | Python |

Each implementation varies the element size and the isoparametric element degree and stores results as RO-Crates uploaded to RoHub for provenance tracking.

## Shared Benchmark Package

Reusable semantic benchmark, RO-Crate, and RoHub helpers are provided by the external Python package `semantic-benchmark`. The environment files and `requirements.txt` install it directly from:

```text
git+https://github.com/Simulation-Benchmarks/semantic-benchmark.git
```

The local `provenance/` scripts keep repository-specific configuration and command-line entrypoints for this plate-with-hole benchmark.

## Interactive Benchmark Evaluation

Click the badge to open the pre-built notebook on the NFDI JupyterHub and explore the provenance plots interactively:

[![NFDI](https://nfdi-jupyter.de/images/nfdi_badge.svg)](https://hub.nfdi-jupyter.de/v2/gh/Simulation-Benchmarks/linear-elastic-plate-with-hole/HEAD?system=JSC-Cloud&flavor=xl1nfdi&labpath=notebooks%2Fplate_with_hole.ipynb)

The notebook fetches run data from RoHub and plots the three metrics against element size, grouped by tool and element degree. See [docs/notebook-pipeline.md](docs/notebook-pipeline.md) for details on how the notebook is built.

## License

This repository follows the [REUSE](https://reuse.software/) specification.
License information is provided per file via [REUSE.toml](./REUSE.toml).
In short:

- Source code files (`.py`, `.jl`, `Snakefile*`, `.github/workflows/*.yml`) are licensed under the [MIT License](./LICENSES/MIT.txt).
- Documentation and figures (`.md`, `.svg`) are licensed under [CC-BY-4.0](./LICENSES/CC-BY-4.0.txt).
- Data, configuration, and generated artifacts (`.json`, `.yml`, `.toml`, `.ipynb`, `.zip`) are licensed under [CC0-1.0](./LICENSES/CC0-1.0.txt).

## Citation

Please see [`CITATION.cff`](./CITATION.cff) for citation metadata, including the concept DOI and versioned DOIs archived on Zenodo.
