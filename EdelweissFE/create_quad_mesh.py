"""Create a quadrilateral mesh of the benchmark domain for EdelweissFE.

The benchmark ships a shared ``create_mesh.py`` that all tools use.  EdelweissFE
cannot consume its output directly, for two reasons:

* EdelweissFE's element library provides quadrilateral and hexahedral continuum
  elements only -- there is no triangular plane element.  The ``cell_type`` of
  every benchmark configuration is ``triangle``, so the triangulation has to be
  recombined into quadrilaterals here.
* For a second order ansatz, gmsh emits complete nine-node quadrilaterals,
  whereas EdelweissFE offers the eight-node serendipity element ``CPS8R``.
  Asking gmsh for *incomplete* second order elements yields the eight-node
  quads.

Geometry, physical groups and element size are identical to the shared script, so
the meshes remain comparable with the other tools of the benchmark.
"""

import json
from argparse import ArgumentParser

import gmsh
from pint import UnitRegistry

ureg = UnitRegistry()


def create_mesh(parameter_file: str, mesh_file: str) -> None:
    with open(parameter_file) as f:
        parameters = json.load(f)

    # Read configuration from parameters instead of the filename
    configuration = parameters["configuration"]

    length = ureg.Quantity(parameters["length[m]"], "m").to_base_units().magnitude
    radius = ureg.Quantity(parameters["radius[m]"], "m").to_base_units().magnitude
    # create mesh with gmsh python api
    r"""
    4---------3
    |         |
    5_        |
      \       |
       1______2

    """

    gmsh.initialize()
    gmsh.model.add(configuration)

    element_size = (
        ureg.Quantity(parameters["element_size[m]"], "m").to_base_units().magnitude
    )

    gmsh.option.setNumber("Mesh.CharacteristicLengthMin", element_size)
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", element_size)
    gmsh.option.setNumber("Mesh.CharacteristicLengthFactor", 1.0)

    element_degree = parameters["isoparametric_element_degree"]
    if element_degree not in (1, 2):
        raise ValueError(
            f"Unsupported isoparametric_element_degree '{element_degree}'. "
            "EdelweissFE provides CPS4 (degree 1) and CPS8R (degree 2)."
        )
    gmsh.option.setNumber("Mesh.ElementOrder", element_degree)
    # CPS8R is the eight-node serendipity quad, so drop the interior node of
    # the complete nine-node element.
    gmsh.option.setNumber("Mesh.SecondOrderIncomplete", 1)

    z = 0.0
    lc = 1.0

    x0 = 0.0
    x1 = x0 + radius
    x2 = x0 + length
    y0 = 0.0
    y1 = y0 + radius
    y2 = y0 + length

    center = gmsh.model.geo.addPoint(x0, y0, z, lc)
    p1 = gmsh.model.geo.addPoint(x1, y0, z, lc)
    p2 = gmsh.model.geo.addPoint(x2, y0, z, lc)
    p3 = gmsh.model.geo.addPoint(x2, y2, z, lc)
    p4 = gmsh.model.geo.addPoint(x0, y2, z, lc)
    p5 = gmsh.model.geo.addPoint(x0, y1, z, lc)

    l1 = gmsh.model.geo.addLine(p1, p2)
    l2 = gmsh.model.geo.addLine(p2, p3)
    l3 = gmsh.model.geo.addLine(p3, p4)
    l4 = gmsh.model.geo.addLine(p4, p5)
    l5 = gmsh.model.geo.addCircleArc(p5, center, p1)

    curve = gmsh.model.geo.addCurveLoop([l1, l2, l3, l4, l5])
    plane = gmsh.model.geo.addPlaneSurface([curve])

    # Recombine the triangular facets into quadrilaterals on this surface.
    gmsh.model.geo.mesh.setRecombine(2, plane)

    gmsh.model.geo.synchronize()
    gmsh.model.geo.removeAllDuplicates()
    gmsh.model.addPhysicalGroup(2, [plane], 1, name="surface")
    gmsh.model.addPhysicalGroup(1, [l4], 1, name="boundary_left")
    gmsh.model.addPhysicalGroup(1, [l1], 2, name="boundary_bottom")
    gmsh.model.addPhysicalGroup(1, [l2], 3, name="boundary_right")
    gmsh.model.addPhysicalGroup(1, [l3], 4, name="boundary_top")

    # Frontal-Delaunay for quads plus full-quad recombination, so that no
    # triangle survives anywhere in the domain.
    gmsh.option.setNumber("Mesh.Algorithm", 8)
    gmsh.option.setNumber("Mesh.RecombineAll", 1)
    gmsh.option.setNumber("Mesh.RecombinationAlgorithm", 2)

    gmsh.model.mesh.generate(2)
    gmsh.write(mesh_file)
    gmsh.finalize()


if __name__ == "__main__":
    PARSER = ArgumentParser(
        description="Create a quadrilateral mesh for the EdelweissFE simulation"
    )
    PARSER.add_argument(
        "--input_parameter_file",
        required=True,
        help="JSON file containing simulation parameters",
    )
    PARSER.add_argument(
        "--output_mesh_file",
        required=True,
        help="Output path for the generated mesh (.msh)",
    )
    ARGS = vars(PARSER.parse_args())
    create_mesh(ARGS["input_parameter_file"], ARGS["output_mesh_file"])
