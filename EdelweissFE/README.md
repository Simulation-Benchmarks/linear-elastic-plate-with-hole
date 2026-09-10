# EdelweissFE

[EdelweissFE](https://github.com/EdelweissFE/EdelweissFE) implementation of the
*linear-elastic plate with hole* benchmark. The workflow follows the same layout
as the other tools of this repository: `run_benchmark.py` turns the semantic
benchmark description into one `parameters_<configuration>.json` per
configuration and runs the Snakemake workflow for each of them in
`results/<configuration>/`, producing `solution_metrics.json` and
`solution_field_data.zip`.

## Running the benchmark

```
mamba env create -f environment_benchmark.yml
conda run -n edelweissfe-model-validation python run_benchmark.py \
    --benchmark-file ../benchmark/1.0.0/minimal-configurations.json \
    --benchmark-zip ../benchmark/1.0.0/linear-elastic-plate-with-hole.zip \
    --result-path results
```

`analytical_solution.py`, `create_mesh.py` and `environment_mesh.yml` are taken
from the benchmark archive and are therefore not part of this directory in the
repository.

EdelweissFE itself is not installed into a conda environment. The workflow
declares an [Apptainer image](https://github.com/Edelweiss-Numerics/EdelweissFE-Apptainer)
for the simulation rule, which Snakemake pulls into `apptainer_envs/`.

## Workflow

| Rule | Script | Purpose |
| ---- | ------ | ------- |
| `create_mesh` | `create_quad_mesh.py` | quadrilateral gmsh mesh of the domain |
| `convert_mesh` | `convert_mesh.py` | Abaqus-like mesh include and the Neumann boundary faces |
| `create_simulation_input` | `create_edelweiss_input.py` | input file and the traction loads |
| `run_simulation` | -- | `edelweissfe input.inp` inside the container |
| `create_metrics` | `create_metrics.py` | benchmark metrics and the zipped Ensight export |

## Deviations from the benchmark description

EdelweissFE cannot express every detail of the benchmark exactly. The following
choices were made, and they have to be kept in mind when comparing the metrics
with the other tools:

* **Quadrilateral instead of triangular cells.** The element library of
  EdelweissFE provides quadrilateral and hexahedral continuum elements only,
  while every benchmark configuration requests `cell_type: triangle`.
  `create_quad_mesh.py` therefore recombines the triangulation into
  quadrilaterals. At a given `element_size` the mesh is not the same as the one
  the other tools use.
* **Eight-node quadrilaterals with reduced integration.** Degree 1 uses `CPS4`,
  which is fully integrated with 2x2 points. For
  `isoparametric_element_degree: 2` the element is `CPS8R`, the eight-node
  serendipity element with the reduced 2x2 rule: EdelweissFE has neither a
  nine-node Lagrange quadrilateral nor a fully integrated plane stress element
  of second order. The maximum von Mises stress is therefore sampled further
  away from the hole than with the other tools.
* **Face-wise constant traction.** A distributed load of EdelweissFE carries a
  constant magnitude per surface, so the analytical traction is evaluated at the
  centre of every element face of the Neumann boundary and applied as a
  face-wise constant surface traction. This is a midpoint-rule approximation of
  the boundary term of the weak form.
* **Reaction force from the nodal right hand side.** The reaction force on the
  left boundary is the sum of the nodal right-hand-side entries of the
  constrained degrees of freedom, as in the Kratos implementation, rather than
  an integral of the traction over the boundary. The external load acting on the
  top left corner node is not part of that sum.
* **Approximated L2 error.** As in the Kratos implementation, the L2 norm of the
  displacement error is approximated from the nodal errors weighted by the cell
  areas, not by quadrature of the error field.
