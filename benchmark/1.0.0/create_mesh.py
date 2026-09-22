import json
from argparse import ArgumentParser

import gmsh
from pint import UnitRegistry

ureg = UnitRegistry()


def create_mesh(parameter_file, element_category, mesh_file):
    # Load parameters
    with open(parameter_file) as f:
        parameters = json.load(f)

    # Read configuration from parameters instead of the filename
    configuration = parameters["configuration"]

    length = (
        ureg.Quantity(parameters["length[m]"], "m")
        .to_base_units()
        .magnitude
    )
    radius = (
        ureg.Quantity(parameters["radius[m]"], "m")
        .to_base_units()
        .magnitude
    )
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
        ureg.Quantity(parameters["element_size[m]"], "m")
        .to_base_units()
        .magnitude
    )
    
    gmsh.option.setNumber("Mesh.CharacteristicLengthMin", element_size)
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", element_size)
    gmsh.option.setNumber("Mesh.CharacteristicLengthFactor", 1.0)
    gmsh.option.setNumber("Mesh.ElementOrder", parameters["isoparametric_element_degree"])
    
    cell_type = parameters["cell_type"]
    
    if cell_type != "triangle" and cell_type != "quadrilateral":
        raise ValueError(
            f"Unsupported cell_type '{cell_type}'. Use one of: triangle, quadrilateral."
        )

    if element_category not in ("lagrange", "serendipity"):
        raise ValueError(
            f"Unsupported element_category '{element_category}'. Use one of: lagrange, serendipity."
        )

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

    if cell_type == "quadrilateral":
        # Recombine triangular facets into quadrilateral elements on this surface.
        gmsh.model.geo.mesh.setRecombine(2, plane)
        # Frontal-Delaunay for quads plus full-quad recombination, so that no
        # triangle survives anywhere in the domain.
        gmsh.option.setNumber("Mesh.Algorithm", 8)
        gmsh.option.setNumber("Mesh.RecombineAll", 1)
        gmsh.option.setNumber("Mesh.RecombinationAlgorithm", 2)
        
        # Drop the interior node of the complete nine-node second-order quad,
        # yielding the eight-node serendipity element
        if parameters["isoparametric_element_degree"] == 2 and element_category == "serendipity":
            gmsh.option.setNumber("Mesh.SecondOrderIncomplete", 1)
    

    gmsh.model.geo.synchronize()
    gmsh.model.geo.removeAllDuplicates()
    gmsh.model.addPhysicalGroup(2, [plane], 1, name="surface")
    gmsh.model.addPhysicalGroup(1, [l4], 1, name="boundary_left")
    gmsh.model.addPhysicalGroup(1, [l1], 2, name="boundary_bottom")
    gmsh.model.addPhysicalGroup(1, [l2], 3, name="boundary_right")
    gmsh.model.addPhysicalGroup(1, [l3], 4, name="boundary_top")

    gmsh.model.mesh.generate(2)
    gmsh.write(mesh_file)
    gmsh.finalize()


if __name__ == "__main__":
    PARSER = ArgumentParser(description="Create input files and mesh for FEniCS simulation")
    PARSER.add_argument("--input_parameter_file", required=True, help="JSON file containing simulation parameters")
    PARSER.add_argument("--element_category", default="lagrange", type=str, help="Either a lagrange or a serendipity element (default: lagrange)")
    PARSER.add_argument("--output_mesh_file", required=True, help="Output path for the generated mesh (.msh)")
    ARGS = vars(PARSER.parse_args())
    create_mesh(ARGS["input_parameter_file"], ARGS["element_category"], ARGS["output_mesh_file"])