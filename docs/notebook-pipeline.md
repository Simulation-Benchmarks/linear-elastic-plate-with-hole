# Notebook pipeline

The `notebooks/plate_with_hole.ipynb` notebook in this repository is
**auto-generated** on every push to `main` (and on manual
`workflow_dispatch`).

## Inputs

- Documentation: `docs/plate-with-hole.md`
- Postprocessing script: `scripts/postprocess_plate.py` (source of
  truth for the code cells)
- Output: `notebooks/plate_with_hole.ipynb`

## How it works

The workflow at `.github/workflows/merge-docs-to-notebooks.yml` runs
`scripts/build_notebook.py`, which:

1. Reads the documentation markdown.
2. Parses the postprocessing script with `ast.parse` and embeds each
   top-level definition as a code cell. The `if __name__ == "__main__":`
   guard is stripped so the cell runs end-to-end when the notebook is
   opened.
3. Prepends the documentation as a markdown cell (with a Binder badge).
4. Writes the result as a Jupyter notebook to the output path.

The result is committed back to `main` with `[skip ci]`.

## Regenerating locally

    python scripts/build_notebook.py \
      --doc docs/plate-with-hole.md \
      --script scripts/postprocess_plate.py \
      --notebook notebooks/plate_with_hole.ipynb \
      --repo Simulation-Benchmarks/linear-elastic-plate-with-hole \
      --branch main
