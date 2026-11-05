from pathlib import Path

SOFTWARE_VERSION = str(config.get("software_version", "1.12.0"))
JULIA_IMAGE = "docker://julia:1.12.2-bookworm"
WORKFLOW_DIR = Path(workflow.basedir).resolve()
BENCHMARK_DIR = Path(
    config.get(
        "benchmark_dir",
        WORKFLOW_DIR.parents[1] if WORKFLOW_DIR.parent.name == "results" else WORKFLOW_DIR,
    )
).resolve()
SHARED_PROJECT_DIR = BENCHMARK_DIR / "julia_depot" / "project"


rule setup_all:
    input: str(SHARED_PROJECT_DIR / "Manifest.toml")


rule stage_julia_project:
    input: str(BENCHMARK_DIR / "Project.toml")
    output: project=str(SHARED_PROJECT_DIR / "Project.toml")
    params: project_dir=str(SHARED_PROJECT_DIR)
    shell:
        """
        mkdir -p {params.project_dir:q}
        cp {input:q} {output.project:q}
        """


rule setup_julia_environment:
    input: project=str(SHARED_PROJECT_DIR / "Project.toml")
    output: manifest=str(SHARED_PROJECT_DIR / "Manifest.toml")
    params:
        software_version=SOFTWARE_VERSION,
        project_dir=str(SHARED_PROJECT_DIR),
    container: JULIA_IMAGE
    shell:
        """
        julia --project={params.project_dir:q} -e 'using Pkg; Pkg.add(Pkg.PackageSpec(name="ExtendableFEM", version="{params.software_version}")); Pkg.instantiate()'
        """
