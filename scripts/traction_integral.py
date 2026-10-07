"""Traction integral over the left boundary, postprocessed from stored results.

Computes F = int_{x=0} sigma(u_h) n ds with n = (-1, 0), i.e. the force that the
left support exerts on the plate, identically for every tool. The geometry and
the connectivity come from the gmsh mesh `mesh.msh` of a configuration, the
nodal displacements from the field output of the tool, matched to the mesh
nodes by their coordinates. The stress is evaluated with the isoparametric shape
functions of the cell adjacent to each boundary edge and integrated with Gauss
quadrature along the edge.

Supported cells are the three- and six-node triangles and the four- and
eight-node quadrilaterals. The tool is detected from its output files:

    FEniCSx        solution_field_data_displacements_*_p0_000000.vtu  (u)
    Kratos         vtk/*.vtk                                           (DISPLACEMENT)
    EdelweissFE    esExport.case                                       (displacement)
    ExtendableFEM  results_*.vtu                                       (u_x, u_y)

Usage:

    python scripts/traction_integral.py <results dir> [...] [--output traction.json]

Every directory below the given ones that holds a `parameters.json` and a
`mesh.msh` is treated as one configuration. Requires numpy, scipy, meshio and
pyvista.
"""

import json
from argparse import ArgumentParser
from pathlib import Path

import meshio
import numpy as np
import pyvista
from scipy.spatial import cKDTree

GAUSS_POINTS, GAUSS_WEIGHTS = np.polynomial.legendre.leggauss(8)

TRIANGLE_CORNERS = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
QUAD_CORNERS = np.array([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]])


def triangle3(xi, eta):
    """Shape functions and their reference derivatives of the linear triangle."""
    shape = np.array([1.0 - xi - eta, xi, eta])
    derivatives = np.array([[-1.0, -1.0], [1.0, 0.0], [0.0, 1.0]])
    return shape, derivatives


def triangle6(xi, eta):
    """Quadratic triangle, corners first, then the mid-side nodes 01, 12, 20."""
    l = np.array([1.0 - xi - eta, xi, eta])
    dl = np.array([[-1.0, -1.0], [1.0, 0.0], [0.0, 1.0]])
    shape = np.concatenate((l * (2.0 * l - 1.0), 4.0 * l * np.roll(l, -1)))
    corner_derivatives = (4.0 * l - 1.0)[:, None] * dl
    mid_derivatives = 4.0 * (l[:, None] * np.roll(dl, -1, axis=0) + np.roll(l, -1)[:, None] * dl)
    return shape, np.vstack((corner_derivatives, mid_derivatives))


def quad4(xi, eta):
    """Bilinear quadrilateral."""
    a, b = QUAD_CORNERS[:, 0], QUAD_CORNERS[:, 1]
    shape = 0.25 * (1.0 + a * xi) * (1.0 + b * eta)
    derivatives = 0.25 * np.column_stack((a * (1.0 + b * eta), b * (1.0 + a * xi)))
    return shape, derivatives


def quad8(xi, eta):
    """Serendipity quadrilateral, corners first, then the mid-side nodes 01, 12, 23, 30."""
    a, b = QUAD_CORNERS[:, 0], QUAD_CORNERS[:, 1]
    corner_shape = 0.25 * (1.0 + a * xi) * (1.0 + b * eta) * (a * xi + b * eta - 1.0)
    corner_derivatives = 0.25 * np.column_stack(
        (a * (1.0 + b * eta) * (2.0 * a * xi + b * eta), b * (1.0 + a * xi) * (a * xi + 2.0 * b * eta))
    )
    mid_shape = np.array([
        0.5 * (1.0 - xi**2) * (1.0 - eta),
        0.5 * (1.0 + xi) * (1.0 - eta**2),
        0.5 * (1.0 - xi**2) * (1.0 + eta),
        0.5 * (1.0 - xi) * (1.0 - eta**2),
    ])
    mid_derivatives = np.array([
        [-xi * (1.0 - eta), -0.5 * (1.0 - xi**2)],
        [0.5 * (1.0 - eta**2), -eta * (1.0 + xi)],
        [-xi * (1.0 + eta), 0.5 * (1.0 - xi**2)],
        [-0.5 * (1.0 - eta**2), -eta * (1.0 - xi)],
    ])
    return np.concatenate((corner_shape, mid_shape)), np.vstack((corner_derivatives, mid_derivatives))


ELEMENTS = {
    "triangle": (triangle3, TRIANGLE_CORNERS),
    "triangle6": (triangle6, TRIANGLE_CORNERS),
    "quad": (quad4, QUAD_CORNERS),
    "quad8": (quad8, QUAD_CORNERS),
}


def read_displacement(config_dir: Path):
    """Return the output points and the nodal displacements of a configuration."""
    if fenics := sorted(config_dir.glob("solution_field_data_displacements_*_p0_000000.vtu")):
        mesh = pyvista.read(fenics[0])
        displacement = np.asarray(mesh.point_data["u"])[:, :2]
    elif kratos := sorted(config_dir.glob("vtk/*.vtk")):
        mesh = pyvista.read(kratos[0])
        displacement = np.asarray(mesh.point_data["DISPLACEMENT"])[:, :2]
    elif (case := config_dir / "esExport.case").exists():
        reader = pyvista.EnSightReader(str(case))
        reader.set_active_time_set(1)
        reader.set_active_time_point(len(reader.time_values) - 1)
        mesh = reader.read()["all"]
        displacement = np.asarray(mesh.point_data["displacement"])[:, :2]
    elif extendablefem := sorted(config_dir.glob("results_*.vtu")):
        mesh = pyvista.read(extendablefem[0])
        displacement = np.column_stack((mesh.point_data["u_x"], mesh.point_data["u_y"]))
    else:
        raise FileNotFoundError(f"No supported displacement output in {config_dir}")
    return np.asarray(mesh.points)[:, :2], displacement


def analytical_reaction_x(parameters: dict) -> float:
    """Exact x-component, -int_a^l sigma_xx(0, y) dy, of the Kirsch solution."""
    a, l, p = parameters["radius[m]"], parameters["length[m]"], parameters["load[Pa]"]
    return -p * (l - a + 0.5 * a * (1.0 - a / l) + 0.5 * a * (1.0 - a**3 / l**3))


def traction_integral(config_dir: Path) -> dict:
    """Integrate sigma(u_h) n over the left boundary x = 0 of one configuration."""
    with open(config_dir / "parameters.json") as f:
        parameters = json.load(f)
    E = parameters["youngs_modulus[Pa]"]
    nu = parameters["poissons_ratio"]
    # Plane stress in Voigt notation (xx, yy, xy) with engineering shear strain.
    stiffness = E / (1.0 - nu**2) * np.array([[1.0, nu, 0.0], [nu, 1.0, 0.0], [0.0, 0.0, 0.5 * (1.0 - nu)]])

    mesh = meshio.read(config_dir / "mesh.msh")
    points = mesh.points[:, :2]
    output_points, output_displacement = read_displacement(config_dir)
    distance, index = cKDTree(output_points).query(points)
    # Single precision output (Kratos VTK) is off by about 1e-8 m.
    if distance.max() > 1e-6 * parameters["length[m]"] or len(np.unique(index)) != len(index):
        raise ValueError(f"Output nodes of {config_dir} do not match mesh.msh")
    displacement = output_displacement[index]

    cell_type = next(block.type for block in mesh.cells if block.type in ELEMENTS)
    cells = np.vstack([block.data for block in mesh.cells if block.type == cell_type])
    shape_functions, corners = ELEMENTS[cell_type]
    on_left = np.isclose(points[:, 0], 0.0, atol=1e-10 * parameters["length[m]"])

    force = np.zeros(2)
    for cell in cells:
        coordinates = points[cell]
        nodal_displacement = displacement[cell]
        for a in range(len(corners)):
            b = (a + 1) % len(corners)
            if not (on_left[cell[a]] and on_left[cell[b]]):
                continue
            half_edge = 0.5 * (corners[b] - corners[a])
            for s, weight in zip(GAUSS_POINTS, GAUSS_WEIGHTS):
                _, derivatives = shape_functions(*(corners[a] + (s + 1.0) * half_edge))
                jacobian = coordinates.T @ derivatives
                gradient = nodal_displacement.T @ derivatives @ np.linalg.inv(jacobian)
                strain = np.array([gradient[0, 0], gradient[1, 1], gradient[0, 1] + gradient[1, 0]])
                sxx, syy, sxy = stiffness @ strain
                length_element = np.linalg.norm(jacobian @ half_edge)
                # The outward normal of the left boundary is (-1, 0).
                force += weight * length_element * np.array([-sxx, -sxy])

    exact_x = analytical_reaction_x(parameters)
    return {
        "configuration": parameters.get("configuration", config_dir.name),
        "cell_type": cell_type,
        "element_size[m]": parameters["element_size[m]"],
        "isoparametric_element_degree": parameters["isoparametric_element_degree"],
        "traction_integral_left_boundary_x[N]": float(force[0]),
        "traction_integral_left_boundary_y[N]": float(force[1]),
        "error_x[N]": float(force[0] - exact_x),
        "error_y[N]": float(force[1]),
    }


def main() -> None:
    parser = ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("results", nargs="+", type=Path, help="result directories to search")
    parser.add_argument("--output", type=Path, help="JSON file for the results")
    args = parser.parse_args()

    config_dirs = sorted(
        {p.parent for root in args.results for p in root.rglob("parameters.json") if (p.parent / "mesh.msh").exists()}
    )
    results = []
    for config_dir in config_dirs:
        result = {"path": str(config_dir), **traction_integral(config_dir)}
        results.append(result)
        print(
            f"{result['configuration']:>14}  {result['cell_type']:9}  p={result['isoparametric_element_degree']}"
            f"  h={result['element_size[m]']:<9}  Fx={result['traction_integral_left_boundary_x[N]']:+.6e}"
            f"  error x={result['error_x[N]']:+.3e}  Fy={result['traction_integral_left_boundary_y[N]']:+.3e}"
        )
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
