"""Postprocessing for the linear-elastic plate with a hole benchmark.

This script is the source of truth for the postprocessing logic. The
notebooks/plate_with_hole.ipynb notebook is auto-generated from this
file plus docs/plate-with-hole.md by the merge-docs-to-notebooks GitHub
Actions workflow (see docs/notebook-pipeline.md).
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_DIRS = [
    REPO_ROOT / "fenics",
    REPO_ROOT / "kratos",
    REPO_ROOT / "extendablefem",
]


def locate_metric_files(tool_dirs=TOOL_DIRS):
    """Walk each tool's results/ tree and return a list of
    (tool, config, metrics_path) tuples for every solution_metrics.json
    found.
    """
    metric_files = []
    for tool_dir in tool_dirs:
        if not tool_dir.exists():
            continue
        results_dir = tool_dir / "results"
        if not results_dir.exists():
            continue
        for config_dir in sorted(p for p in results_dir.iterdir() if p.is_dir()):
            for metrics_path in config_dir.rglob("solution_metrics.json"):
                metric_files.append((tool_dir.name, config_dir.name, metrics_path))
    return metric_files


def load_metrics(metric_files):
    """Load each solution_metrics.json into a row of a DataFrame."""
    rows = []
    for tool, config, path in metric_files:
        with open(path) as f:
            metrics = json.load(f)
        rows.append(
            {
                "tool": tool,
                "config": config,
                **{k: metrics.get(k) for k in metrics},
            }
        )
    df = pd.DataFrame(rows)
    return df.sort_values(["tool", "config"]).reset_index(drop=True)


def plot_von_mises_convergence(df, ax=None):
    """Plot max von Mises stress vs. configuration, one line per tool.

    The relevant metric in `solution_metrics.json` is
    `max_von_mises_stress[Pa]`. The y-axis is log-scaled; the expected
    behaviour is a decreasing trend as the element size `h` shrinks.
    """
    show = ax is None
    if show:
        fig, ax = plt.subplots(figsize=(8, 5))
    if "max_von_mises_stress[Pa]" in df.columns:
        for tool, sub in df.groupby("tool"):
            sub = sub.sort_values("config")
            ax.plot(
                sub["config"],
                sub["max_von_mises_stress[Pa]"],
                marker="o",
                label=tool,
            )
    ax.set_xlabel("Configuration (mesh refinement)")
    ax.set_ylabel("Max von Mises stress [Pa]")
    ax.set_yscale("log")
    ax.set_title("Convergence: max von Mises stress vs. mesh refinement")
    ax.legend()
    ax.grid(True, which="both", ls="--", alpha=0.3)
    if show:
        fig.tight_layout()
        plt.show()


def plot_top_right_displacement(df, ax=None):
    """Plot the top-right corner displacement vs. configuration.

    The `displacement_top_right_corner[m]` metric is a 2-vector
    `[ux, uy]`. Both components are plotted per tool to confirm that the
    solution converges to the analytical Kirsch solution.
    """
    show = ax is None
    if show:
        fig, ax = plt.subplots(figsize=(8, 5))
    disp_col = "displacement_top_right_corner[m]"
    if disp_col in df.columns:
        for tool, sub in df.groupby("tool"):
            sub = sub.sort_values("config")
            ux = [d[0] if d is not None else float("nan") for d in sub[disp_col]]
            uy = [d[1] if d is not None else float("nan") for d in sub[disp_col]]
            ax.plot(sub["config"], ux, marker="o", label=f"{tool} ux")
            ax.plot(
                sub["config"],
                uy,
                marker="s",
                linestyle="--",
                label=f"{tool} uy",
            )
    ax.set_xlabel("Configuration")
    ax.set_ylabel("Displacement [m]")
    ax.set_title("Top-right corner displacement convergence")
    ax.legend()
    ax.grid(True, ls="--", alpha=0.3)
    if show:
        fig.tight_layout()
        plt.show()


if __name__ == "__main__":
    metric_files = locate_metric_files()
    print(f"Found {len(metric_files)} metric files across all tools.")
    df = load_metrics(metric_files)
    print(df)
    plot_von_mises_convergence(df)
    plot_top_right_displacement(df)
