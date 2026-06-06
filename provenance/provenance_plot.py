"""Plotting utilities for benchmark provenance query results."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Sequence

import matplotlib.pyplot as plt


class ProvenancePlotter:
    """Plot provenance metric series from query results."""

    @staticmethod
    def _finish_plot(
        x_axis_label: str,
        y_axis_label: str,
        title: str,
        x_ticks: Sequence[float],
        output_file: str | None,
    ) -> None:
        """Apply common plot formatting and save or display the result."""
        plt.xlabel(x_axis_label)
        plt.ylabel(y_axis_label)
        plt.title(title)
        plt.grid(True)
        plt.xscale("log")
        plt.xticks(ticks=x_ticks, labels=[str(x) for x in x_ticks], rotation=45)
        plt.tight_layout()

        if output_file:
            plt.savefig(output_file)
            print(f"Plot saved to: {output_file}")
        else:
            plt.show()

    def plot_provenance_graph(
        self,
        data: Sequence[Sequence[Any]],
        x_axis_label: str,
        y_axis_label: str,
        group_index: int,
        x_axis_index: int,
        y_axis_index: int,
        title: str,
        output_file: str | None = None,
        figsize: tuple[int, int] = (12, 5),
    ) -> None:
        """Plot grouped metric series from RoHub provenance query results."""
        grouped_values: dict[str, list[tuple[float, float]]] = defaultdict(list)
        x_tick_set = set()

        for row in data:
            group = str(row[group_index])
            x_value = float(row[x_axis_index])
            y_value = float(row[y_axis_index])

            grouped_values[group].append((x_value, y_value))
            x_tick_set.add(x_value)

        plt.figure(figsize=figsize)

        for group, values in grouped_values.items():
            values.sort()
            x_values, y_values = zip(*values)
            plt.plot(x_values, y_values, marker="o", linestyle="-", label=group)

        if grouped_values:
            plt.legend()

        self._finish_plot(
            x_axis_label,
            y_axis_label,
            title,
            sorted(x_tick_set),
            output_file,
        )
