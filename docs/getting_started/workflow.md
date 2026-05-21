# Terminologies

## Parameter JSON File

A `parameter_*.json` file defines all the user-adjustable parameters for mesh generation, material properties, boundary conditions, and solver settings for finite element simulations. Each parameter file represents a unique configuration of these parameters that will be processed by the workflow system, e.g. [parameter_1.json](https://github.com/BAMresearch/NFDI4IngModelValidationPlatform/blob/main/benchmarks/linear-elastic-plate-with-hole/parameters_1.json).

```json
{   
    "configuration": "1",    
}
```

The keyword `"configuration"` is a unique identifier for the provided parameter set. It is used in output folder naming and must be unique across all parameter files.

## Mesh Generation

The `create_mesh.py` file contains the code for mesh generation. In case the mesh(es) are already available, the file is not needed. In the `linear-elastic-plate-with-hole` example the [create_mesh.py](https://github.com/BAMresearch/NFDI4IngModelValidationPlatform/blob/main/benchmarks/linear-elastic-plate-with-hole/create_mesh.py) file:

1. receives inputs from `\parameter_*.json` and outputs `.msh` files.
2. Uses `gmsh` library for mesh generation.
3. Uses `pint` library for unit conversion to the SI units.

## Environment Files

The environment files are YML files which configures the environment for running a script. They contain a list of software libraries that build up an environment. They are present inside the simulation tool's folder for the tool-specific scripts and inside the benchmark folder for common scripts.
```shell
benchmarks/
    ├── linear-elastic-plate-with-hole/
        ├── environment_mesh.yml
        ├── fenics
            ├── environment_simulation.yml
        ├── kratos
            ├── environment_simulation.yml
```