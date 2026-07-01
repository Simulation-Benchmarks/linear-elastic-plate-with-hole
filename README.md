# Infinite Plate with Hole Benchmark

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

## Interactive Benchmark Evaluation

Click the badge to open the pre-built notebook on the NFDI JupyterHub and explore the provenance plots interactively:

[![NFDI](https://nfdi-jupyter.de/images/nfdi_badge.svg)](https://hub.nfdi-jupyter.de/v2/gh/Simulation-Benchmarks/linear-elastic-plate-with-hole/HEAD?system=JSC-Cloud&flavor=xl1nfdi&labpath=notebooks%2Fplate_with_hole.ipynb)

The notebook fetches run data from RoHub and plots the three metrics against element size, grouped by tool and element degree. See [docs/notebook-pipeline.md](docs/notebook-pipeline.md) for details on how the notebook is built.
