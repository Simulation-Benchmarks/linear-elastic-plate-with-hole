SOFTWARE_VERSION = str(config["software_version"])
JULIA_IMAGE = "docker://julia:1.12.2-bookworm"

rule setup_julia_environment:
    input: "Project.toml"
    output: manifest="Manifest.toml"
    params: software_version=SOFTWARE_VERSION
    container: JULIA_IMAGE
    shell:
        """
        julia --project=. -e 'using Pkg; Pkg.add(Pkg.PackageSpec(name="ExtendableFEM", version="{params.software_version}")); Pkg.instantiate()'
        """
