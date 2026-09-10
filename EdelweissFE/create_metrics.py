"""Extract the benchmark metrics from the EdelweissFE Ensight export.

The metrics and their names are the ones defined by the semantic benchmark, so
that the results can be compared with the other tools of this repository.
"""

import json
import zipfile
from argparse import ArgumentParser
from pathlib import Path
from typing import cast

import numpy as np
import pyvista
from pint import UnitRegistry

from analytical_solution import AnalyticalSolution


def create_metrics(
    parameter_file: str,
    case_file: str,
    metrics_file: str,
    solution_file_zip: str,
) -> None:
    ureg = UnitRegistry()
    with open(parameter_file) as f:
        parameters = json.load(f)
    configuration = parameters["configuration"]

    youngs_modulus = (
        ureg.Quantity(parameters["youngs_modulus[Pa]"], "Pa").to_base_units().magnitude
    )
    poissons_ratio = (
        ureg.Quantity(parameters["poissons_ratio"], "").to_base_units().magnitude
    )
    radius = ureg.Quantity(parameters["radius[m]"], "m").to_base_units().magnitude
    length = ureg.Quantity(parameters["length[m]"], "m").to_base_units().magnitude
    load = ureg.Quantity(parameters["load[Pa]"], "Pa").to_base_units().magnitude

    analytical_solution = AnalyticalSolution(
        E=youngs_modulus,
        nu=poissons_ratio,
        radius=radius,
        L=length,
        load=load,
    )

    reader = pyvista.EnSightReader(case_file)
    reader.set_active_time_set(1)
    reader.set_active_time_point(len(reader.time_values) - 1)
    mesh = cast(pyvista.DataSet, reader.read()["all"])

    coords = np.asarray(mesh.points)
    displacement = np.asarray(mesh.point_data["displacement"])[:, :2]

    # Compare the discrete displacement field with the analytical solution.
    u_ref_x, u_ref_y = analytical_solution.displacement(coords[:, :2].T)
    u_ref = np.column_stack((np.asarray(u_ref_x), np.asarray(u_ref_y)))
    error_squared_nodes = np.sum((displacement - u_ref) ** 2, axis=1)
    max_displacement_error_nodes = float(
        np.max(np.linalg.norm(displacement - u_ref, axis=1))
    )

    # Approximate the L2 norm of the error by integrating the nodal error over
    # the cells, as the other tools of the benchmark do.
    cell_areas = np.asarray(
        mesh.compute_cell_sizes(length=False, area=True, volume=False).cell_data["Area"]
    )
    l2_error_squared = 0.0
    for cell in range(mesh.n_cells):
        point_ids = mesh.get_cell(cell).point_ids
        if len(point_ids) == 0:
            continue
        l2_error_squared += float(
            np.mean(error_squared_nodes[point_ids]) * cell_areas[cell]
        )
    l2_error_displacement = float(np.sqrt(l2_error_squared))

    # The nodal field 'P' holds the element contributions to the right hand side,
    # i.e. the negative internal forces. On the constrained dofs of the left
    # boundary those balance the support reaction.
    tolerance = 1e-10 * max(1.0, length)
    left_boundary = np.isclose(coords[:, 0], 0.0, atol=tolerance)
    reaction = -np.asarray(mesh.point_data["reaction_force"])[:, :2]
    reaction_force_left_boundary_x = float(np.sum(reaction[left_boundary, 0]))
    reaction_force_left_boundary_y = float(np.sum(reaction[left_boundary, 1]))

    # The top right corner is a node of the mesh, so no interpolation is needed.
    corner = mesh.find_closest_point([length, length, 0.0])
    displacement_top_right_corner = [
        float(displacement[corner, 0]),
        float(displacement[corner, 1]),
    ]

    # The von Mises stress is evaluated at the quadrature points and reduced to
    # the element maximum by the field output of EdelweissFE.
    max_von_mises_stress = float(np.max(mesh.cell_data["von_mises_stress"]))

    metrics = {
        "number_of_dofs[-]": int(mesh.n_points * 2),
        "max_von_mises_stress[Pa]": max_von_mises_stress,
        "l2_error_displacement[m]": l2_error_displacement,
        "max_displacement_error[m]": max_displacement_error_nodes,
        "reaction_force_left_boundary_x[N]": reaction_force_left_boundary_x,
        "reaction_force_left_boundary_y[N]": reaction_force_left_boundary_y,
        "displacement_top_right_corner[m]": displacement_top_right_corner,  # [ux, uy]
    }
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=4)

    # The Ensight export is a case file plus a directory of geometry and
    # variable files, so keep the relative layout inside the archive.
    case_path = Path(case_file)
    field_data = [case_path] + sorted(case_path.with_suffix("").glob("*"))
    with zipfile.ZipFile(solution_file_zip, "w") as archive:
        for path in field_data:
            archive.write(
                path,
                arcname=str(Path(configuration) / path.relative_to(case_path.parent)),
            )


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Extract the benchmark metrics from the EdelweissFE results."
    )
    parser.add_argument(
        "--input_parameter_file",
        required=True,
        help="JSON file containing simulation parameters (input)",
    )
    parser.add_argument(
        "--input_case_file",
        required=True,
        help="Path to the Ensight case file written by EdelweissFE (input)",
    )
    parser.add_argument(
        "--output_solution_file_zip",
        required=True,
        help="Path to the zipped solution files (output)",
    )
    parser.add_argument(
        "--output_metrics_file",
        required=True,
        help="Path to the output metrics JSON file (output)",
    )
    args, _ = parser.parse_known_args()
    create_metrics(
        args.input_parameter_file,
        args.input_case_file,
        args.output_metrics_file,
        args.output_solution_file_zip,
    )
