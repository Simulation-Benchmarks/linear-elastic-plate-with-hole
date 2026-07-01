# Notebook pipeline

The `notebooks/benchmark-results.ipynb` notebook in this repository is
**auto-generated** on every push to `main` (and on manual
`workflow_dispatch`).

## Inputs

- Documentation: `docs/benchmark-documentation.md`
- Source notebook: `notebooks/RoCrate.ipynb` (source of truth for the
  code cells)
- Output: `notebooks/benchmark-results.ipynb`

## How it works

The workflow at `.github/workflows/merge-docs-to-notebooks.yml` runs
`scripts/build_notebook.py`, which:

1. Reads the documentation markdown.
2. Prepends the documentation as a markdown cell (with a Binder badge).
3. Appends all cells from `notebooks/RoCrate.ipynb` verbatim (cell type
   preserved, outputs cleared).
4. Writes the result as a Jupyter notebook to the output path.

The result is committed back to `main` with `[skip ci]`.

## Regenerating locally

    python scripts/build_notebook.py \
<<<<<<< HEAD
      --doc docs/benchmark-documentation.md \
      --script scripts/postprocess_plate.py \
      --notebook notebooks/benchmark-results.ipynb \
=======
      --doc docs/plate-with-hole.md \
      --source-notebook notebooks/RoCrate.ipynb \
      --notebook notebooks/plate_with_hole.ipynb \
>>>>>>> main
      --repo Simulation-Benchmarks/linear-elastic-plate-with-hole \
      --branch main
