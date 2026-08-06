# Notebook pipeline

The `notebooks/benchmark-results.ipynb` notebook in this repository is
**auto-generated** by [repo2docker](https://github.com/jupyterhub/repo2docker)'s
`postBuild` hook, which runs whenever the repository image is built (e.g. on
launch via Binder or the NFDI JupyterHub).

## Inputs

- Documentation: `docs/benchmark-documentation.md`
- Source notebook: `notebooks/RoCrate.ipynb` (source of truth for the
  code cells)
- Output: `notebooks/benchmark-results.ipynb`

## How it works

The `postBuild` script at the repo root runs `scripts/build_notebook.py`,
which:

1. Reads the documentation markdown.
2. Prepends the documentation as a markdown cell, rewriting any relative
   image paths so they still resolve from the notebook's directory.
3. Appends all cells from `notebooks/RoCrate.ipynb` verbatim (cell type
   preserved, outputs cleared).
4. Writes the result as a Jupyter notebook to the output path.

Because this runs as part of the repo2docker build, the notebook is always
freshly generated for anyone launching the repository interactively — there
is no CI step and nothing to commit back to `main`.

`notebooks/plate_with_hole.ipynb` is git-ignored: it is a build artifact,
not a source file, and only exists once `postBuild` (or a local run of the
script below) has generated it.

## Regenerating locally

    python scripts/build_notebook.py \
      --doc docs/benchmark-documentation.md \
      --source-notebook notebooks/RoCrate.ipynb \
      --notebook notebooks/benchmark-results.ipynb \
