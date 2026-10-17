import json
import pyvista
from pathlib import Path
import zipfile
from argparse import ArgumentParser
import numpy as np
from pint import UnitRegistry
import sys
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analytical_solution import AnalyticalSolution

# Symmetric 7-point, degree-5 Gauss quadrature rule on the reference triangle
# {(xi, eta): xi >= 0, eta >= 0, xi + eta <= 1} (Dunavant 1985). Weights sum to 1
# and are scaled by the reference triangle's area (0.5) when used.
_QUADRATURE_POINTS = np.array(
    [
        [1.0 / 3.0, 1.0 / 3.0],
        [0.0597158717, 0.4701420641],
        [0.4701420641, 0.0597158717],
        [0.4701420641, 0.4701420641],
        [0.7974269853, 0.1012865073],
        [0.1012865073, 0.7974269853],
        [0.1012865073, 0.1012865073],
    ]
)
_QUADRATURE_WEIGHTS = np.array(
    [0.225, 0.1323941527, 0.1323941527, 0.1323941527, 0.1259391805, 0.1259391805, 0.1259391805]
)
_REFERENCE_TRIANGLE_AREA = 0.5


def _triangle_shape_functions(xi, eta, n_nodes):
    """
    Shape functions and their reference-coordinate derivatives for a straight- or
    curved-sided triangle, evaluated at (xi, eta), following the VTK node ordering:
    3 corner nodes, followed (for 6-node elements) by the mid-edge nodes on edges
    (0-1), (1-2), (2-0).
    """
    l1, l2, l3 = 1.0 - xi - eta, xi, eta
    if n_nodes == 3:
        N = np.array([l1, l2, l3])
        dN_dxi = np.array([-1.0, 1.0, 0.0])
        dN_deta = np.array([-1.0, 0.0, 1.0])
        return N, dN_dxi, dN_deta
    if n_nodes == 6:
        N = np.array(
            [
                l1 * (2.0 * l1 - 1.0),
                l2 * (2.0 * l2 - 1.0),
                l3 * (2.0 * l3 - 1.0),
                4.0 * l1 * l2,
                4.0 * l2 * l3,
                4.0 * l3 * l1,
            ]
        )
        # dl1 = (-1, -1), dl2 = (1, 0), dl3 = (0, 1)
        dN_dxi = np.array(
            [
                -(4.0 * l1 - 1.0),
                4.0 * l2 - 1.0,
                0.0,
                4.0 * (l1 - l2),
                4.0 * l3,
                -4.0 * l3,
            ]
        )
        dN_deta = np.array(
            [
                -(4.0 * l1 - 1.0),
                0.0,
                4.0 * l3 - 1.0,
                -4.0 * l2,
                4.0 * l2,
                4.0 * (l1 - l3),
            ]
        )
        return N, dN_dxi, dN_deta
    raise ValueError(f"Unsupported triangle with {n_nodes} nodes; expected 3 or 6.")


def _l2_error_squared_displacement(mesh, displacement, analytical_solution):
    """
    Integrates the squared displacement error over the mesh using isoparametric
    Gauss quadrature on each triangle, exact to the element's own interpolation
    degree (matching how Fenics assembles its L2 error via ufl.dx). This is required
    for quadratic (isoparametric_element_degree=2) elements: a naive vertex/nodal
    average is not a valid quadrature rule for a P2 field and silently caps the
    observed convergence order at that of a linear element.
    """
    coords = np.asarray(mesh.points)[:, :2]

    # Group cells by node count so each group's quadrature points can be evaluated
    # in one batched call to analytical_solution.displacement, rather than once per
    # quadrature point per cell (meshes at the finest resolutions have 10^5+ cells).
    point_ids_by_type = {3: [], 6: []}
    for i in range(mesh.n_cells):
        point_ids = np.asarray(mesh.get_cell(i).point_ids)
        if len(point_ids) in point_ids_by_type:
            point_ids_by_type[len(point_ids)].append(point_ids)

    l2_error_sq = 0.0
    for n_nodes, point_id_lists in point_ids_by_type.items():
        if not point_id_lists:
            continue
        point_ids = np.array(point_id_lists)  # (n_cells, n_nodes)
        node_coords = coords[point_ids]  # (n_cells, n_nodes, 2)
        node_displacement = displacement[point_ids]  # (n_cells, n_nodes, 2)

        for (xi, eta), weight in zip(_QUADRATURE_POINTS, _QUADRATURE_WEIGHTS):
            N, dN_dxi, dN_deta = _triangle_shape_functions(xi, eta, n_nodes)
            x_phys = np.einsum("n,cnd->cd", N, node_coords)
            dx_dxi, dy_dxi = np.einsum("n,cnd->cd", dN_dxi, node_coords).T
            dx_deta, dy_deta = np.einsum("n,cnd->cd", dN_deta, node_coords).T
            det_j = dx_dxi * dy_deta - dy_dxi * dx_deta

            u_fe = np.einsum("n,cnd->cd", N, node_displacement)
            u_ref_x, u_ref_y = analytical_solution.displacement(x_phys.T)
            err_sq = (u_fe[:, 0] - u_ref_x) ** 2 + (u_fe[:, 1] - u_ref_y) ** 2

            l2_error_sq += np.sum(weight * _REFERENCE_TRIANGLE_AREA * np.abs(det_j) * err_sq)

    return float(l2_error_sq)


def postprocess_results(input_parameter_file, input_result_vtk, output_metrics_file, output_solution_file_zip):
    ureg = UnitRegistry()
    with open(input_parameter_file) as f:
        parameters = json.load(f)
    config = parameters["configuration"]

    mesh = pyvista.read(str(input_result_vtk))
    if not isinstance(mesh, pyvista.DataSet):
        raise TypeError(f"Expected a pyvista.DataSet, got {type(mesh).__name__}")
    mesh = cast(pyvista.DataSet, mesh)

    E = (
        ureg.Quantity(
            parameters["youngs_modulus[Pa]"], "Pa"
        )
        .to_base_units()
        .magnitude
    )
    nu = (
        ureg.Quantity(
            parameters["poissons_ratio"], ""
        )
        .to_base_units()
        .magnitude
    )
    radius = (
        ureg.Quantity(parameters["radius[m]"], "m")
        .to_base_units()
        .magnitude
    )
    L = (
        ureg.Quantity(parameters["length[m]"], "m")
        .to_base_units()
        .magnitude
    )
    load = (
        ureg.Quantity(parameters["load[Pa]"], "Pa")
        .to_base_units()
        .magnitude
    )

    analytical_solution = AnalyticalSolution(
        E=E,
        nu=nu,
        radius=radius,
        L=L,
        load=load,
    )
    # Compute maximum von Mises stress at Gauss points.
    max_von_mises_stress_gauss_points = 0
    for key, values in mesh.cell_data.items():
        if "VON_MISES_STRESS" in key:
            max_von_mises_stress_gauss_points = float(np.max(values))
            break
    
    # Compute L2 error of displacement field compared to analytical solution.
    coords = np.asarray(mesh.points)
    displacement = np.asarray(mesh.point_data["DISPLACEMENT"])[:, :2]
    u_ref_x, u_ref_y = analytical_solution.displacement(coords[:, :2].T)
    u_ref = np.column_stack((np.asarray(u_ref_x), np.asarray(u_ref_y)))

    l2_error_sq = _l2_error_squared_displacement(mesh, displacement, analytical_solution)
    l2_error_displacement = float(np.sqrt(l2_error_sq))

    # Compute reaction forces on the left boundary (x=0) by summing the reaction forces at the nodes on that boundary.
    # Note: Kratos REACTION variable represents force exerted BY structure ON constraint, 
    # so we negate to get the standard FEA convention (constraint force ON structure).
    tolerance = 1e-10 * max(1.0, L)
    left_boundary_mask = np.isclose(coords[:, 0], 0.0, atol=tolerance)
    reaction = np.asarray(mesh.point_data.get("REACTION", np.zeros((mesh.n_points, 3))))
    reaction_force_left_boundary_x = float(np.sum(reaction[left_boundary_mask, 0]))
    reaction_force_left_boundary_y = float(np.sum(reaction[left_boundary_mask, 1]))

    # Compute displacement at the top-right corner
    probe_points = pyvista.PolyData(
        np.array([[1.0, 1.0, 0.0]], dtype=float)
    )
    sampled = probe_points.sample(mesh)
    displacement_sampled = sampled.point_data.get("DISPLACEMENT")
    if displacement_sampled is None:
        closest_id = mesh.find_closest_point([1.0, 1.0, 0.0])
        displacement_at_evaluation_point = [float(displacement[closest_id, 0]), float(displacement[closest_id, 1])]
    else:
        displacement_at_evaluation_point = [float(displacement_sampled[0, 0]), float(displacement_sampled[0, 1])]

    # Compute nodal displacement error (Euclidean norm of error vector at each node)
    nodal_displacement_error = np.linalg.norm(displacement - u_ref, axis=1)
    max_displacement_error_nodes = float(np.max(nodal_displacement_error))
    
    # Compute the number of dofs
    num_dofs = int(mesh.n_points * 2)

    metrics = {
        "number_of_dofs[-]": num_dofs,
        "max_von_mises_stress[Pa]": max_von_mises_stress_gauss_points,
        "l2_error_displacement[m]": l2_error_displacement,
        "max_displacement_error[m]": max_displacement_error_nodes,
        "reaction_force_left_boundary_x[N]": reaction_force_left_boundary_x,
        "reaction_force_left_boundary_y[N]": reaction_force_left_boundary_y,
        "displacement_top_right_corner[m]": displacement_at_evaluation_point,  # [ux, uy]
    }
    with open(output_metrics_file, "w") as f:
        json.dump(metrics, f, indent=4)
        
    files_to_store = [str(input_result_vtk)]

    with zipfile.ZipFile(output_solution_file_zip, "w") as zipf:
        for filepath in files_to_store:
            zipf.write(filepath, arcname=f"result_{config}.vtk")

if __name__ == "__main__":
    parser = ArgumentParser(
        description="Postprocess Kratos results and write metrics and zipped solution."
    )
    parser.add_argument(
        "--input_parameter_file",
        required=True,
        help="JSON file containing simulation parameters (input)",
    )
    parser.add_argument(
        "--input_result_vtk",
        required=True,
        help="Path to the Kratos result VTK file (input)",
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

    postprocess_results(
        args.input_parameter_file,
        args.input_result_vtk,
        args.output_metrics_file,
        args.output_solution_file_zip
    )
