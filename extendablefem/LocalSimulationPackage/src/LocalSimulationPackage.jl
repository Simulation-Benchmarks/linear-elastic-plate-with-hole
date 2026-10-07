#This package is only for precompiling the actual simulation code to speedup benchmark runs.
module LocalSimulationPackage

using JSON, StructUtils
using Gmsh
using ExtendableGrids
using ExtendableFEM
using StaticArrays: @SArray
using LinearAlgebra
using ZipArchives: ZipWriter, zip_newfile
using PrecompileTools: @setup_workload, @compile_workload
using Triangulate
using SimplexGridFactory

export run_simulation

struct PlateConfig
    id::String
    F::Float64
    E::Float64
    ν::Float64
    radius::Float64
    length::Float64
    element_order::Int64
end

function parse_config(configfile::String)
    config = JSON.parsefile(configfile)
    id = config["configuration"]
    F = config["load[Pa]"]
    E = config["youngs_modulus[Pa]"]
    ν = config["poissons_ratio"]
    radius = config["radius[m]"]
    length = config["length[m]"]
    element_order = config["isoparametric_element_degree"]
    return PlateConfig(id, F, E, ν, radius, length, element_order)
end


@tags struct Metrics
    ndofs::Int64 & (json = (name = "number_of_dofs[-]",),)
    max_von_mises_stress::Float64 & (json = (name = "max_von_mises_stress[Pa]",),)
    L2_error::Float64 & (json = (name = "l2_error_displacement[m]",),)
    max_displacement_error::Float64 & (json = (name = "max_displacement_error[m]",),)
    reaction_force_left_boundary_x::Float64 & (json = (name = "reaction_force_left_boundary_x[N]",),)
    reaction_force_left_boundary_y::Float64 & (json = (name = "reaction_force_left_boundary_y[N]",),)
    displacement_top_right_corner::Tuple{Float64, Float64} & (json = (name = "displacement_top_right_corner[m]",),)
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

function reaction_force_kernel!(result, ∇u, qpinfo)
    sig = zeros(4)
    sigma!(sig, ∇u, qpinfo)
    σ = tensor_view(sig, 1, TDMatrix(2))
    traction = σ * qpinfo.normal
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

function setup_problem(config::PlateConfig)
    PD = ProblemDescription("Linear elastic 2D Plate with hole, configuration " * config.id)
    u = Unknown("u"; name = "displacement")
    assign_unknown!(PD, u)

    assign_operator!(PD, BilinearOperator(sigma!, [grad(u)]; params = [config.E, config.ν]))
    assign_operator!(PD, LinearOperator(traction_right_kernel!, [id(u)]; entities = ON_BFACES, regions = [3], params = [config.radius, config.F]))
    assign_operator!(PD, LinearOperator(traction_top_kernel!, [id(u)]; entities = ON_BFACES, regions = [4], params = [config.radius, config.F]))
    assign_operator!(PD, HomogeneousBoundaryData(u; regions = [1], mask = [1, 0]))
    assign_operator!(PD, HomogeneousBoundaryData(u; regions = [2], mask = [0, 1]))
    return PD, u
end

function solve_problem(config::PlateConfig, grid::ExtendableGrid, PD, u)
    FEType = H1Pk{2, 2, config.element_order}
    FES = FESpace{FEType}(grid)
    u_h = solve(PD, FES; timeroutputs = :hide)
    u_ex = FEVector(FES; name = "exact solution")
    interpolate!(u_ex.FEVectorBlocks[1], ON_CELLS, u_ex_kernel!; params = [config.radius, config.F, config.E, config.ν])
    metrics = calculate_metrics(config, u, FES, u_h, u_ex)
    return u_h, u_ex, metrics
end

function calculate_metrics(config::PlateConfig, u, FES, u_h, u_ex)

    SquaredErrorIntegrationExact = ItemIntegrator(exact_squared_error!, [id(u)]; quadorder = 8, params = [config.radius, config.F, config.E, config.ν])
    squared_error = evaluate(SquaredErrorIntegrationExact, u_h)
    L2error = sqrt(sum(squared_error))

    vonMisesIntegration = ItemIntegrator(vonMises!, [grad(u)]; quadorder = 3, params = [config.E, config.ν])
    vonMises_stresses = evaluate(vonMisesIntegration, u_h)
    max_displacement_error = maximum(
        [maximum(abs.(nodevalues(u_h[u])[1, :] - nodevalues(u_ex.FEVectorBlocks[1])[1, :])), maximum(abs.(nodevalues(u_h[u])[2, :] - nodevalues(u_ex.FEVectorBlocks[1])[2, :]))]
    )
    reaction_force_left_boundary = [0.0, 0.0]

    LeftBoundaryTractionIntegrator = ItemIntegratorDG(reaction_force_kernel!, [grad(u)]; resultdim = 2, entities = ON_BFACES, regions = [1], params = [config.E, config.ν])
    rflb = evaluate(LeftBoundaryTractionIntegrator, u_h)

    reaction_force_left_boundary[1] = sum(rflb[1, :])
    reaction_force_left_boundary[2] = sum(rflb[2, :])

    displacement_top_right_corner = [0.0, 0.0]

    evaluate!(displacement_top_right_corner, PointEvaluator([id(u)], u_h), [config.length, config.length])

    metrics = Metrics(
        FES.ndofs,
        maximum(vonMises_stresses),
        L2error,
        max_displacement_error,
        reaction_force_left_boundary[1],
        reaction_force_left_boundary[2],
        (displacement_top_right_corner[1], displacement_top_right_corner[2])
    )
    return metrics
end

function output_results(config::PlateConfig, grid::ExtendableGrid, u_h, u_ex, outputzip::String, outputmetrics::String)

    u_x = nodevalues(u_h[1])[1, :]
    u_y = nodevalues(u_h[1])[2, :]
    u_exx = nodevalues(u_ex.FEVectorBlocks[1])[1, :]
    u_exy = nodevalues(u_ex.FEVectorBlocks[1])[2, :]

    u_mag = sqrt.(u_x .* u_x .+ u_y .* u_y)
    uex_mag = sqrt.(u_exx .* u_exx .+ u_exy .* u_exy)

    outputvtk = "results_" * config.id * ".vtu"
    writeVTK(outputvtk, grid; compress = false, u_x = u_x, u_y = u_y, u_mag = u_mag, uexx = u_exx, uexy = u_exy, uex = uex_mag)
    f = open(outputvtk, "r")
    vtkcontent = read(f, String)
    return ZipWriter(outputzip) do w
        zip_newfile(w, "result_" * config.id * ".vtu"; compress = true)
        write(w, vtkcontent)
    end

end

function solve_plate_with_hole(config::PlateConfig, grid::ExtendableGrid)
    # bfacemask!(grid, [0.0, 0.0], [config.radius, config.radius], 50) #not needed I think
    PD, u = setup_problem(config)
    u_h, u_ex, metrics = solve_problem(config, grid, PD, u)
    return u_h, u_ex, metrics
end

function run_simulation(configfile::String, meshfile::String, outputzip::String, outputmetrics::String)
    config = parse_config(configfile)
    grid = simplexgrid_from_gmsh(meshfile)
    u_h, u_ex, metrics = solve_plate_with_hole(config, grid)
    output_results(config, grid, u_h, u_ex, outputzip, outputmetrics)
    JSON.json(outputmetrics, metrics; pretty = true)
    return
end


function create_grid(config::PlateConfig)
    H = config.length
    R = config.radius
    n_points_on_circle = 6

    builder = SimplexGridBuilder(Generator = Triangulate)
    p1 = point!(builder, H, 0)
    p2 = point!(builder, H, H)
    p3 = point!(builder, 0, H)
    points = [point!(builder, R * sin(t), R * cos(t)) for t in range(0, π / 2; length = n_points_on_circle)]
    facetregion!(builder, 1)
    facet!(builder, points[end], p1)
    facetregion!(builder, 2)
    facet!(builder, p1, p2)
    facetregion!(builder, 3)
    facet!(builder, p2, p3)
    facetregion!(builder, 4)
    facet!(builder, p3, points[1])
    facetregion!(builder, 5)
    for i in 1:(n_points_on_circle - 1)
        facet!(builder, points[i], points[i + 1])
    end
    return simplexgrid(builder, maxvolume = 1.0)
end


@setup_workload begin
    config = PlateConfig("precompile", 100000000.0, 210000000000.0, 0.3, 0.33, 1.0, 1)
    outgrid = create_grid(config)
    gridfile = "tmp_precompile.msh"
    simplexgrid_to_gmsh(outgrid; filename = gridfile)
    grid = simplexgrid_from_gmsh(gridfile)
    @compile_workload begin
        u_h, u_ex, metrics = solve_plate_with_hole(config, grid)
    end
    rm(gridfile)
end


end # module LocalSimulationPackage
