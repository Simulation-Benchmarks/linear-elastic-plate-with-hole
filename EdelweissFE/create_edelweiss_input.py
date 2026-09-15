"""Build the EdelweissFE input file and the Neumann load definitions.

The benchmark prescribes the traction of the analytical Kirsch solution on the
right and top boundary.  EdelweissFE applies a distributed load with a constant
magnitude per surface, so the traction is evaluated at the centre of every
element face of the Neumann boundary and applied as a face-wise constant surface
traction -- a midpoint-rule approximation of the boundary integral.
"""

import json
from argparse import ArgumentParser

import numpy as np
from pint import UnitRegistry

from analytical_solution import AnalyticalSolution

ureg = UnitRegistry()

# Number of quadrature points of the elements chosen in convert_mesh.py: CPS4
# integrates fully with 2x2 points, CPS8R uses the same reduced 2x2 rule.
QUADRATURE_POINTS = {1: 4, 2: 4}


def create_edelweiss_input(
    parameter_file: str,
    template_file: str,
    neumann_faces_file: str,
    input_file: str,
    neumann_loads_file: str,
) -> None:
    with open(parameter_file) as f:
        parameters = json.load(f)
    with open(neumann_faces_file) as f:
        neumann_faces = json.load(f)

    youngs_modulus = (
        ureg.Quantity(parameters["youngs_modulus[Pa]"], "Pa").to_base_units().magnitude
    )
    poissons_ratio = (
        ureg.Quantity(parameters["poissons_ratio"], "").to_base_units().magnitude
    )
    radius = ureg.Quantity(parameters["radius[m]"], "m").to_base_units().magnitude
    length = ureg.Quantity(parameters["length[m]"], "m").to_base_units().magnitude
    load = ureg.Quantity(parameters["load[Pa]"], "Pa").to_base_units().magnitude

    element_degree = parameters["isoparametric_element_degree"]
    if element_degree not in QUADRATURE_POINTS:
        raise ValueError(
            f"Unsupported isoparametric_element_degree '{element_degree}'. "
            "EdelweissFE provides CPS4 (degree 1) and CPS8R (degree 2)."
        )

    analytical_solution = AnalyticalSolution(
        E=youngs_modulus,
        nu=poissons_ratio,
        radius=radius,
        L=length,
        load=load,
    )

    centres = np.array([face["centre"] for face in neumann_faces], dtype=float)
    normals = np.array([face["normal"] for face in neumann_faces], dtype=float)

    sxx, sxy, syy = analytical_solution.stress(centres.T)
    traction_x = sxx * normals[:, 0] + sxy * normals[:, 1]
    traction_y = sxy * normals[:, 0] + syy * normals[:, 1]

    with open(neumann_loads_file, "w") as f:
        for face, t_x, t_y in zip(neumann_faces, traction_x, traction_y):
            # The solver looks the step action up by its lower case module
            # name, so 'distributedload' must not be camel cased here.
            f.write(
                f"distributedload, name=load_{face['surface']}, "
                f"surface={face['surface']}, type=surface traction, "
                f'magnitude="{t_x:.16e},{t_y:.16e}"\n'
            )

    replacements = {
        "_YOUNGS_MODULUS_": repr(youngs_modulus),
        "_POISSONS_RATIO_": repr(poissons_ratio),
        "_N_QUADRATURE_POINTS_": str(QUADRATURE_POINTS[element_degree]),
    }

    with open(template_file) as f:
        template = f.read()
    for placeholder, value in replacements.items():
        if placeholder not in template:
            raise ValueError(f"Placeholder {placeholder} missing in {template_file}.")
        template = template.replace(placeholder, value)

    with open(input_file, "w") as f:
        f.write(template)


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Create the EdelweissFE input file and its Neumann load include."
    )
    parser.add_argument(
        "--input_parameter_file",
        required=True,
        help="JSON file containing simulation parameters (input)",
    )
    parser.add_argument(
        "--input_template_file",
        required=True,
        help="Path to the EdelweissFE input template (input)",
    )
    parser.add_argument(
        "--input_neumann_faces_file",
        required=True,
        help="Path to the JSON description of the Neumann boundary faces (input)",
    )
    parser.add_argument(
        "--output_input_file",
        required=True,
        help="Path to the EdelweissFE input file (output)",
    )
    parser.add_argument(
        "--output_neumann_loads_file",
        required=True,
        help="Path to the include file holding the distributed loads (output)",
    )
    args, _ = parser.parse_known_args()
    create_edelweiss_input(
        args.input_parameter_file,
        args.input_template_file,
        args.input_neumann_faces_file,
        args.output_input_file,
        args.output_neumann_loads_file,
    )
