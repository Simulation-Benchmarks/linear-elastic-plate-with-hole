using JSON, StructUtils
using Fire
using Gmsh
using ExtendableGrids
using ExtendableFEM
using StaticArrays: @SArray
using Unitful
using LinearAlgebra
using ZipArchives: ZipWriter, zip_newfile

struct PlateConfig
    id::String
    F::Float64
    E::Float64
    ν::Float64
    radius::Float64
    length::Float64
    element_order::Int64
end

@tags struct Metrics
    ndofs::Int64 & (json = (name = "numer_of_dofs[-]",),)
    max_von_mises_stress::Float64 & (json = (name = "max_von_mises_stress[Pa]",),)
    L2_error::Float64 & (json = (name = "l2_error_displacement[m]",),)
    max_displacement_error::Float64 & (json = (name = "max_displacement_error[m]",),)
    reaction_force_left_boundary_x::Float64 & (json = (name = "reaction_force_left_boundary_x[N]",),)
    reaction_force_left_boundary_y::Float64 & (json = (name = "reaction_force_left_boundary_y[N]",),)
    displacement_top_right_corner::Tuple{Float64, Float64} & (json = (name = "displacement_top_right_corner[m]",),)
end

#function value_with_unit(json::JSON.Object{String,Any})
#    res = uparse(string(json["value"])*json["unit"])
#    return res
#end


function parse_config(configfile::String)
    config = JSON.parsefile(configfile)
    id = config["configuration"]
    F = config["load[Pa]"] #ustrip(u"Pa",value_with_unit(config["load[Pa]"]))
    E = config["youngs_modulus[Pa]"] #ustrip(u"Pa",value_with_unit(config["young_modulus[Pa]"]))
    ν = config["poissons_ratio"]
    radius = config["radius[m]"] #ustrip(u"m",value_with_unit(config["radius[m]"]))
    length = config["length[m]"] #ustrip(u"m",value_with_unit(config["length[m]"]))
    element_order = config["isoparametric_element_degree"]
    return PlateConfig(id, F, E, ν, radius, length, element_order)
end

function sigma_exact(r, θ, a, T)
    cos2t = cos(2 * θ)
    cos4t = cos(4 * θ)
    sin2t = sin(2 * θ)
    sin4t = sin(4 * θ)

    fac1 = a^2 / (r^2)
    fac2 = T * 1.5 * fac1 * fac1

    sxx = T - T * fac1 * (1.5 * cos2t + cos4t) + fac2 * cos4t
    syy = -T * fac1 * (0.5 * cos2t - cos4t) - fac2 * cos4t
    sxy = -T * fac1 * (0.5 * sin2t + sin4t) + fac2 * sin4t

    return sxx, sxy, syy
end

function traction_right_kernel!(result, qpinfo)
    x = qpinfo.x[1]
    y = qpinfo.x[2]
    r = sqrt(x^2 + y^2)
    θ = atan(y, x)
    sxx, sxy, _ = sigma_exact(r, θ, qpinfo.params[1], qpinfo.params[2])
    result[1] = sxx
    result[2] = sxy
    return nothing
end


function traction_top_kernel!(result, qpinfo)
    x = qpinfo.x[1]
    y = qpinfo.x[2]
    r = sqrt(x^2 + y^2)
    θ = atan(y, x)
    _, sxy, syy = sigma_exact(r, θ, qpinfo.params[1], qpinfo.params[2])
    result[1] = sxy
    result[2] = syy
    return nothing
end

const II = [1 0;0 1]

function sigma!(result, ∇u, qpinfo)
    E = qpinfo.params[1]
    ν = qpinfo.params[2]
    ∇u[2] = (∇u[2] + ∇u[3]) * 0.5
    ∇u[3] = ∇u[2]

    ε = tensor_view(∇u, 1, TDMatrix(2))
    σ = tensor_view(result, 1, TDMatrix(2))
    σ .= ((1.0 - ν) .* ε + ν * tr(ε) .* II) * E / (1 - ν^2)
    return nothing
end

function vonMises!(result, ∇u, qpinfo)
    sig = zeros(4)
    sv = zeros(4)
    sigma!(sig, ∇u, qpinfo)
    σ = tensor_view(sig, 1, TDMatrix(2))
    s = tensor_view(sv, 1, TDMatrix(2))
    p = tr(σ) / 3.0
    s .= σ - p .* II
    result[1] = sqrt(1.5) * sqrt(dot(sv, sv) + p * p) / qpinfo.volume
    return nothing
end

function reaction_force_kernel!(result,∇u,qpinfo)
    sig = zeros(4)
    sigma!(sig,∇u,qpinfo)
    σ = tensor_view(sig,1,TDMatrix(2))
    traction = σ*qpinfo.normal
    result .= traction
    return nothing
end

function u_ex_kernel!(result, qpinfo)
    x = qpinfo.x[1]
    y = qpinfo.x[2]
    a = qpinfo.params[1]
    T = qpinfo.params[2]
    E = qpinfo.params[3]
    ν = qpinfo.params[4]
    r = sqrt(x^2 + y^2)
    θ = atan(y, x)
    k = (3.0 - ν) / (1.0 + ν)
    Ta_8mu = T * a * (1.0 + ν) / (4.0 * E)
    ct = cos(θ)
    c3t = cos(3.0 * θ)
    st = sin(θ)
    s3t = sin(3.0 * θ)
    fac = 2.0 * (a / r)^3


    result[1] = Ta_8mu * (
        (r / a) * (k + 1.0) * ct
            + 2.0 * (a / r) * ((1.0 + k) * ct + c3t)
            - fac * c3t
    )
    result[2] = Ta_8mu * (
        (r / a) * (k - 3.0) * st
            + 2.0 * (a / r) * ((1.0 - k) * st + s3t)
            - fac * s3t
    )
    return nothing
end

function exact_error!(result, u, qpinfo)
    u_ex_kernel!(result, qpinfo)
    result .-= u
    return nothing
end

function exact_squared_error!(result, u, qpinfo)
    u_ex_kernel!(result, qpinfo)
    result .-= u
    result .= result .^ 2
    return nothing
end

function solve_plate_with_hole(config::PlateConfig, grid::ExtendableGrid, outputzip::String, outputmetrics::String)

    bfacemask!(grid, [0.0, 0.0], [config.radius, config.radius], 50)

    PD = ProblemDescription("Linear elastic 2D Plate with hole, configuration " * config.id)
    u = Unknown("u"; name = "displacement")
    assign_unknown!(PD, u)

    assign_operator!(PD, BilinearOperator(sigma!, [grad(u)]; params = [config.E, config.ν]))
    assign_operator!(PD, LinearOperator(traction_right_kernel!, [id(u)]; entities = ON_BFACES, regions = [3], params = [config.radius, config.F]))
    assign_operator!(PD, LinearOperator(traction_top_kernel!, [id(u)]; entities = ON_BFACES, regions = [4], params = [config.radius, config.F]))
    assign_operator!(PD, HomogeneousBoundaryData(u; regions = [1], mask = [1, 0]))
    assign_operator!(PD, HomogeneousBoundaryData(u; regions = [2], mask = [0, 1]))

    FEType = H1Pk{2, 2, config.element_order}
    FES = FESpace{FEType}(grid)
    sol = solve(PD, FES; timeroutputs = :hide)

    u_ex = FEVector(FES; name = "exact solution")
    interpolate!(u_ex.FEVectorBlocks[1], ON_CELLS, u_ex_kernel!; params = [config.radius, config.F, config.E, config.ν])
    u_exx = nodevalues(u_ex.FEVectorBlocks[1])[1, :]
    u_exy = nodevalues(u_ex.FEVectorBlocks[1])[2, :]

    u_x = nodevalues(sol[u])[1, :]
    u_y = nodevalues(sol[u])[2, :]
    u_mag = sqrt.(u_x .* u_x .+ u_y .* u_y)
    uex_mag = sqrt.(u_exx .* u_exx .+ u_exy .* u_exy)


    SquaredErrorIntegrationExact = ItemIntegrator(exact_squared_error!, [id(u)]; quadorder = 8, params = [config.radius, config.F, config.E, config.ν])
    squared_error = evaluate(SquaredErrorIntegrationExact, sol)
    L2error = sqrt(sum(squared_error))

    vonMisesIntegration = ItemIntegrator(vonMises!, [grad(u)]; quadorder = 3, params = [config.E, config.ν])
    vonMises_stresses = evaluate(vonMisesIntegration, sol)

    max_displacement_error = maximum(
        [maximum(abs.(u_x - u_exx)), maximum(abs.(u_y - u_exy))]
    )

    reaction_force_left_boundary = [0.,0.]
    
    LeftBoundaryTractionIntegrator = ItemIntegratorDG(reaction_force_kernel!, [grad(u)];resultdim=2,entities = ON_BFACES, regions= [1],params = [config.E, config.ν])
    rflb = evaluate(LeftBoundaryTractionIntegrator,sol)

    reaction_force_left_boundary[1] = sum(rflb[1,:])
    reaction_force_left_boundary[2] = sum(rflb[2,:])
    
    displacement_top_right_corner = [0.0, 0.0]

    evaluate!(displacement_top_right_corner,PointEvaluator([id(u)],sol),[config.length,config.length])
        
    metrics = Metrics(
        FES.ndofs,
        maximum(vonMises_stresses),
        L2error,
        max_displacement_error,
        reaction_force_left_boundary[1],
        reaction_force_left_boundary[2],
        (displacement_top_right_corner[1],displacement_top_right_corner[2])
    )
    
    JSON.json(outputmetrics, metrics; pretty = true)

    outputvtk = "results_" * config.id * ".vtu" #splitdir(outputzip)[1]*"/results_"*config.id*".vtu";
    writeVTK(outputvtk, grid; compress = false, u_x = u_x, u_y = u_y, u_mag = u_mag, uexx = u_exx, uexy = u_exy, uex = uex_mag)
    f = open(outputvtk, "r")
    vtkcontent = read(f, String)
    ZipWriter(outputzip) do w
        zip_newfile(w, "result_" * config.id * ".vtu"; compress = true)
        write(w, vtkcontent)
    end
    return nothing
end

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
    config = parse_config(configfile)
    grid = simplexgrid_from_gmsh(meshfile)
    solve_plate_with_hole(config, grid, outputzip, outputmetrics)
    return
end
