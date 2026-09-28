using Fire
using LocalSimulationPackage

"run linear elastic plate with a hole using ExtendableFEM.jl"
Fire.@main function run_simulation(;
        configfile::String = "",
        meshfile::String = "",
        outputzip::String = "",
        outputmetrics::String = ""
    )
    if (isempty(configfile))
        @error "No configuration file given"
    end
    if (isempty(meshfile))
        @error "No mesh file given"
    end
    if (isempty(outputzip))
        @error "No output zip file given"
    end
    if (isempty(outputmetrics))
        @error "No output metrics file given"
    end
    LocalSimulationPackage.run_simulation(configfile,meshfile,outputzip,outputmetrics)
    return
end
