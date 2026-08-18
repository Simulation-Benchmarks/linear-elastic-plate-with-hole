process create_mesh {
    publishDir "${projectDir}", mode: 'copy'
    conda "${projectDir}/environment_mesh.yml"

    input:
    path script
    path parameters

    output:
    path "mesh.msh"

    script:
    """
    python3 ${script} --input_parameter_file ${parameters} --output_mesh_file mesh.msh
    """
}

process run_simulation {
    publishDir "${projectDir}", mode: 'copy'
    conda "${projectDir}/environment_simulation.yml"

    input:
    path script
    path parameters
    path mesh

    output:
    path "solution_field_data.zip", emit: zip
    path "solution_metrics.json", emit: metrics

    script:
    """
    python3 ${script} --input_parameter_file ${parameters} --input_mesh_file ${mesh} --output_solution_file_zip solution_field_data.zip --output_metrics_file solution_metrics.json
    """
}

workflow {
    parameters_file = file(params.parameters)
    mesh_script = file("${projectDir}/create_mesh.py")
    simulation_script = file("${projectDir}/run_simulation.py")

    mesh = create_mesh(mesh_script, parameters_file)
    run_simulation(simulation_script, parameters_file, mesh)
}
