import json
import os
from pint import UnitRegistry
from argparse import ArgumentParser


def create_kratos_input(
    parameter_file: str,
    mdpa_file: str,
    kratos_input_template_file: str,
    kratos_material_template_file: str,
    kratos_input_file: str,
    kratos_material_file: str,
):
    ureg = UnitRegistry()
    with open(parameter_file) as f:
        parameters = json.load(f)

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

    with open(kratos_material_template_file) as f:
        material_string = f.read()

    material_string = material_string.replace(r'"{{YOUNG_MODULUS}}"', str(E))
    material_string = material_string.replace(r'"{{POISSON_RATIO}}"', str(nu))

    with open(kratos_material_file, "w") as f:
        f.write(material_string)

    with open(kratos_input_template_file) as f:
        project_parameters_string = f.read()
    project_parameters_string = project_parameters_string.replace(
        r"{{MESH_FILE}}", os.path.splitext(mdpa_file)[0]
    )
    project_parameters_string = project_parameters_string.replace(
        r"{{MATERIAL_FILE}}", kratos_material_file
    )
    project_parameters_string = project_parameters_string.replace(r"{{YOUNG_MODULUS}}", str(E))
    project_parameters_string = project_parameters_string.replace(r"{{POISSON_RATIO}}", str(nu))
    project_parameters_string = project_parameters_string.replace(r"{{RADIUS}}", str(radius))
    project_parameters_string = project_parameters_string.replace(r"{{LENGTH}}", str(L))
    project_parameters_string = project_parameters_string.replace(r"{{LOAD}}", str(load))

    output_dir = os.path.join(os.path.dirname(os.path.abspath(kratos_input_file)),"vtk")
    os.makedirs(output_dir, exist_ok=True)
    project_parameters_string = project_parameters_string.replace(r"{{OUTPUT_PATH}}", output_dir)

    with open(kratos_input_file, "w") as f:
        f.write(project_parameters_string)

if __name__ == "__main__":
    parser = ArgumentParser(
        description="Create Kratos input and material files from templates and parameters."
    )
    parser.add_argument(
        "--input_parameter_file",
        required=True,
        help="JSON file containing simulation parameters (input)",
    )
    parser.add_argument(
        "--input_mdpa_file", required=True, help="Path to the MDPA mesh file (input)"
    )
    parser.add_argument(
        "--input_kratos_input_template",
        required=True,
        help="Path to the kratos input template file (input)",
    )
    parser.add_argument(
        "--input_material_template",
        required=True,
        help="Path to the kratos material template file (input)",
    )
    parser.add_argument(
        "--output_kratos_inputfile",
        required=True,
        help="Path to the kratos input file (output)",
    )
    parser.add_argument(
        "--output_kratos_materialfile",
        required=True,
        help="Path to the kratos material file (output)",
    )
    args, _ = parser.parse_known_args()

    create_kratos_input(
        parameter_file=args.input_parameter_file,
        mdpa_file=args.input_mdpa_file,
        kratos_input_template_file=args.input_kratos_input_template,
        kratos_material_template_file=args.input_material_template,
        kratos_input_file=args.output_kratos_inputfile,
        kratos_material_file=args.output_kratos_materialfile,
    )
