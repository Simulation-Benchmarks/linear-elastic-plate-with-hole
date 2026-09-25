# EdelweissFE

[EdelweissFE](https://github.com/EdelweissFE/EdelweissFE) implementation of the
*linear-elastic plate with hole* benchmark. `run_benchmark.py` turns the
semantic benchmark description into one `parameters_<configuration>.json` per
configuration and runs the Snakemake workflow for each of them in
`results/<configuration>/`, producing `solution_metrics.json` and
`solution_field_data.zip`.

## Running the benchmark

```
mamba env create -f environment_benchmark.yml
conda run -n edelweissfe-model-validation python run_benchmark.py \
    --benchmark-file ../benchmark/1.0.0/minimal-configurations.json \
    --result-path results \
    --software-version 26.03
```

`analytical_solution.py`, `create_mesh.py` and `environment_mesh.yml` come from
the benchmark directory alongside `--benchmark-file`, which `run_benchmark.py`
passes on as the resource directory.

The simulation rule runs EdelweissFE from an
[Apptainer image](https://github.com/Edelweiss-Numerics/EdelweissFE-Apptainer),
which Snakemake pulls into `apptainer_envs/`.

## Workflow

| Rule | Script | Purpose |
| ---- | ------ | ------- |
| `create_mesh` | `create_mesh.py` | quadrilateral gmsh mesh of the domain |
| `convert_mesh` | `convert_mesh.py` | Abaqus-like mesh include and the Neumann boundary faces |
| `create_simulation_input` | `create_edelweiss_input.py` | input file and the traction loads |
| `run_simulation` | -- | `edelweissfe input.inp` inside the container |
| `create_metrics` | `create_metrics.py` | benchmark metrics and the zipped Ensight export |

## Deviations from the benchmark description

These choices adapt the benchmark description to EdelweissFE and shape the
metrics:

* **Quadrilateral cells.** The element library covers quadrilateral and
  hexahedral continuum elements, so `run_benchmark.py` runs the configurations
  with `cell_type: quadrilateral` and calls `create_mesh.py` with
  `--element_category serendipity`.
* **Reduced integration at degree 2.** Degree 1 uses `CPS4`, fully integrated
  with 2x2 points. Degree 2 uses `CPS8R`, the eight-node serendipity element
  with the reduced 2x2 rule, so the maximum von Mises stress is sampled at the
  2x2 Gauss points of each element.
* **Face-wise constant traction.** A distributed load carries a constant
  magnitude per surface, so the analytical traction is evaluated at the center
  of every element face of the Neumann boundary and applied face by face. This
  is a midpoint-rule approximation of the boundary term of the weak form.
* **Reaction force from the nodal right hand side.** The reaction force is the
  sum of the nodal right-hand-side entries of the degrees of freedom constrained
  on the left boundary.
* **Approximated L2 error.** The L2 norm of the displacement error is
  approximated from the nodal errors weighted by the cell areas.
