"""Convert the gmsh mesh into the Abaqus-like input EdelweissFE reads.

Besides nodes, elements and the node sets used for the symmetry boundary
conditions, this writes one single-element ``*elset``/``*surface`` pair for every
element face on the Neumann boundary (x = l and y = l).  EdelweissFE applies a
distributed load with a *constant* magnitude per surface, so the traction of the
benchmark -- which varies along the boundary -- has to be applied face by face.
The geometry of those faces is reported in a JSON file, from which
``create_edelweiss_input.py`` builds the actual load definitions.

Element labels are assigned here and nowhere else, so that the surface
definitions and the load definitions cannot get out of sync.
"""

import json
from argparse import ArgumentParser

import meshio
import numpy as np
from pint import UnitRegistry

ureg = UnitRegistry()

# Plane stress elements registered by Marmot, the element provider EdelweissFE
# uses by default. CPS4 integrates fully, CPS8R is the eight-node serendipity
# element with reduced (2x2) integration -- Marmot registers no fully integrated
# plane stress element of second order.
ELEMENT_TYPES = {
    "quad": "CPS4",
    "quad8": "CPS8R",
}

# Local node indices of the element faces, following the Abaqus convention that
# Marmot implements in Spatial2D::Quad4/Quad8::getBoundaryElementIndices().
FACE_NODES = {
    "quad": {1: (0, 1), 2: (1, 2), 3: (2, 3), 4: (3, 0)},
    "quad8": {1: (0, 1, 4), 2: (1, 2, 5), 3: (2, 3, 6), 4: (3, 0, 7)},
}


# Cells of lower dimension that gmsh writes for the physical groups of the
# boundary. They carry no element of the simulation and are dropped.
IGNORED_CELL_TYPES = ("vertex", "line", "line3")


def _wrap(labels, per_line: int = 8) -> str:
    """Format labels as comma separated lines, as Abaqus sets expect."""
    values = [str(label) for label in labels]
    return (
        "\n".join(
            ", ".join(values[start : start + per_line])
            for start in range(0, len(values), per_line)
        )
        + "\n"
    )


def _cell_block(mesh: meshio.Mesh):
    """Return the single block of plane elements, rejecting anything else."""
    blocks = [block for block in mesh.cells if block.type in ELEMENT_TYPES]
    unsupported = {
        block.type
        for block in mesh.cells
        if block.type not in ELEMENT_TYPES and block.type not in IGNORED_CELL_TYPES
    }
    if unsupported:
        raise ValueError(
            f"Unsupported cell types {sorted(unsupported)} in the mesh. EdelweissFE "
            "has no triangular plane element, the mesh must be all-quadrilateral."
        )
    if len(blocks) != 1:
        raise ValueError(
            f"Expected exactly one block of plane elements, found {len(blocks)}."
        )
    return blocks[0]


def convert_mesh(
    parameter_file: str,
    mesh_file: str,
    abaqus_mesh_file: str,
    neumann_faces_file: str,
) -> None:
    with open(parameter_file) as f:
        parameters = json.load(f)

    length = ureg.Quantity(parameters["length[m]"], "m").to_base_units().magnitude

    mesh = meshio.read(mesh_file)
    block = _cell_block(mesh)
    element_type = ELEMENT_TYPES[block.type]

    # Drop the third coordinate and every node that no plane element refers to.
    connectivity = np.asarray(block.data, dtype=int)
    used_nodes = np.unique(connectivity)
    renumber = np.full(len(mesh.points), -1, dtype=int)
    renumber[used_nodes] = np.arange(len(used_nodes))
    connectivity = renumber[connectivity]
    points = np.asarray(mesh.points)[used_nodes, :2]

    x, y = points[:, 0], points[:, 1]

    # Tolerances relative to the span, with a tiny absolute floor.
    x_tol = max(1e-12, 1e-8 * max(1.0, x.max() - x.min()))
    y_tol = max(1e-12, 1e-8 * max(1.0, y.max() - y.min()))

    node_sets = {
        "X_MIN": np.flatnonzero(np.isclose(x, x.min(), atol=x_tol)),
        "X_MAX": np.flatnonzero(np.isclose(x, x.max(), atol=x_tol)),
        "Y_MIN": np.flatnonzero(np.isclose(y, y.min(), atol=y_tol)),
        "Y_MAX": np.flatnonzero(np.isclose(y, y.max(), atol=y_tol)),
    }

    # Collect the element faces on the Neumann boundary together with the
    # outward normal and the face centre, where the traction is evaluated.
    neumann_faces = []
    for local_face, local_nodes in FACE_NODES[block.type].items():
        face_nodes = connectivity[:, local_nodes]
        face_x = points[face_nodes, 0]
        face_y = points[face_nodes, 1]

        on_right = np.all(np.isclose(face_x, length, atol=x_tol), axis=1)
        on_top = np.all(np.isclose(face_y, length, atol=y_tol), axis=1)

        for normal, on_boundary in (((1.0, 0.0), on_right), ((0.0, 1.0), on_top)):
            for element in np.flatnonzero(on_boundary):
                corners = face_nodes[element, :2]
                neumann_faces.append(
                    {
                        "element": int(element) + 1,
                        "face": local_face,
                        "centre": points[corners].mean(axis=0).tolist(),
                        "normal": list(normal),
                    }
                )

    if not neumann_faces:
        raise ValueError("No element face found on the Neumann boundary.")

    for index, face in enumerate(neumann_faces):
        face["element_set"] = f"NEUMANN_E{index:05d}"
        face["surface"] = f"NEUMANN_S{index:05d}"

    with open(abaqus_mesh_file, "w") as f:
        f.write("*node\n")
        for label, point in enumerate(points, start=1):
            f.write(f"{label}, {point[0]:.16e}, {point[1]:.16e}\n")

        f.write(f"*element, type={element_type}\n")
        for label, nodes in enumerate(connectivity, start=1):
            f.write(f"{label}, " + ", ".join(str(node + 1) for node in nodes) + "\n")

        for name, nodes in node_sets.items():
            f.write(f"*nSet, nSet={name}\n")
            f.write(_wrap(nodes + 1))

        for face in neumann_faces:
            f.write(f"*elSet, elSet={face['element_set']}\n")
            f.write(f"{face['element']}\n")

        for face in neumann_faces:
            f.write(f"*surface, name={face['surface']}, type=element\n")
            f.write(f"{face['element_set']}, S{face['face']}\n")

    with open(neumann_faces_file, "w") as f:
        json.dump(neumann_faces, f, indent=4)


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Convert the gmsh mesh to the EdelweissFE input format."
    )
    parser.add_argument(
        "--input_parameter_file",
        required=True,
        help="JSON file containing simulation parameters (input)",
    )
    parser.add_argument(
        "--input_mesh_file", required=True, help="Path to the gmsh mesh file (input)"
    )
    parser.add_argument(
        "--output_mesh_file",
        required=True,
        help="Path to the Abaqus-like mesh include file (output)",
    )
    parser.add_argument(
        "--output_neumann_faces_file",
        required=True,
        help="Path to the JSON description of the Neumann boundary faces (output)",
    )
    args, _ = parser.parse_known_args()
    convert_mesh(
        args.input_parameter_file,
        args.input_mesh_file,
        args.output_mesh_file,
        args.output_neumann_faces_file,
    )
