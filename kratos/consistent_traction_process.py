import sys
from pathlib import Path

import numpy as np

import KratosMultiphysics as KM
import KratosMultiphysics.StructuralMechanicsApplication as SMA

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analytical_solution import AnalyticalSolution

# 4-point Gauss-Legendre quadrature on [-1, 1] (degree-7 exact), used to integrate
# the (non-polynomial) analytical traction along each boundary condition.
_GAUSS_POINTS = np.array([-0.861136311594053, -0.339981043584856, 0.339981043584856, 0.861136311594053])
_GAUSS_WEIGHTS = np.array([0.347854845137454, 0.652145154862546, 0.652145154862546, 0.347854845137454])


def _line_shape_functions(xi, n_nodes):
    """Shape functions and reference derivatives for a 2- or 3-node line, xi in [-1, 1]."""
    if n_nodes == 2:
        N = np.array([0.5 * (1.0 - xi), 0.5 * (1.0 + xi)])
        dN = np.array([-0.5, 0.5])
        return N, dN
    if n_nodes == 3:
        # node order 0, 1 (ends), 2 (mid) -- matches Kratos Line2D3 / meshio "line3"
        N = np.array([0.5 * xi * (xi - 1.0), 0.5 * xi * (xi + 1.0), 1.0 - xi * xi])
        dN = np.array([xi - 0.5, xi + 0.5, -2.0 * xi])
        return N, dN
    raise ValueError(f"Unsupported line with {n_nodes} nodes; expected 2 or 3.")


def Factory(settings, model):
    if not isinstance(settings, KM.Parameters):
        raise Exception("expected input shall be a Parameters object, encapsulating a json string")
    return ConsistentTractionProcess(model, settings["Parameters"])


class ConsistentTractionProcess(KM.Process):
    """
    Applies the exact (spatially-varying) analytical Kirsch-plate traction as a
    properly Gauss-quadrature-integrated consistent nodal load.

    Kratos's built-in assign_vector_variable_to_conditions_process evaluates a
    spatial LINE_LOAD expression once at each condition's centroid and applies
    it as a constant over the whole condition, for both linear and quadratic
    line elements alike. That caps the boundary data's accuracy independent of
    the bulk element order and dominates the global discretization error once
    isoparametric_element_degree=2 is used.

    For every condition in `model_part_name`, this process instead computes its
    own consistent load vector f_i = integral of N_i(xi) * (sigma(x(xi)) . normal)
    * |J(xi)| dxi via Gauss quadrature, and *accumulates* (rather than
    overwrites) the result into each node's POINT_LOAD, so nodes shared between
    differently-normaled boundaries (e.g. the corner between the right and top
    edges) correctly receive the sum of both edges' contributions.
    """

    # Shared across all instances constructed within one simulation process, so
    # a node touched by two boundaries (e.g. the corner) only gets one
    # PointLoadCondition even though two ConsistentTractionProcess instances
    # (one per boundary) both accumulate a force into it.
    _nodes_with_point_load_condition = set()

    def __init__(self, model, settings):
        super().__init__()
        default_settings = KM.Parameters("""
        {
            "model_part_name"    : "please_specify_model_part_name",
            "normal"             : [0.0, 0.0],
            "youngs_modulus[Pa]" : 0.0,
            "poissons_ratio"     : 0.0,
            "radius[m]"          : 0.0,
            "length[m]"          : 0.0,
            "load[Pa]"           : 0.0
        }
        """)
        settings.ValidateAndAssignDefaults(default_settings)

        self.model_part = model[settings["model_part_name"].GetString()]
        self.normal = np.array([settings["normal"][0].GetDouble(), settings["normal"][1].GetDouble()])

        self.analytical_solution = AnalyticalSolution(
            E=settings["youngs_modulus[Pa]"].GetDouble(),
            nu=settings["poissons_ratio"].GetDouble(),
            radius=settings["radius[m]"].GetDouble(),
            L=settings["length[m]"].GetDouble(),
            load=settings["load[Pa]"].GetDouble(),
        )

    def ExecuteInitialize(self):
        root_model_part = self.model_part.GetRootModelPart()
        if not root_model_part.HasNodalSolutionStepVariable(SMA.POINT_LOAD):
            raise RuntimeError(
                "POINT_LOAD is not a registered nodal solution step variable; "
                "add it via the solver's nodal_solution_step_variables settings."
            )

        properties = next(iter(root_model_part.Elements)).Properties

        max_condition_id = max((c.Id for c in root_model_part.Conditions), default=0)

        for condition in self.model_part.Conditions:
            geom = condition.GetGeometry()
            n_nodes = len(geom)
            node_coords = np.array([[node.X, node.Y] for node in geom])
            nodal_forces = np.zeros((n_nodes, 2))

            for xi, weight in zip(_GAUSS_POINTS, _GAUSS_WEIGHTS):
                N, dN = _line_shape_functions(xi, n_nodes)
                x_phys = N @ node_coords
                dx_dxi, dy_dxi = dN @ node_coords
                jacobian = np.hypot(dx_dxi, dy_dxi)

                sxx, sxy, syy = self.analytical_solution.stress(x_phys.reshape(2, 1))
                traction = np.array(
                    [
                        sxx[0] * self.normal[0] + sxy[0] * self.normal[1],
                        sxy[0] * self.normal[0] + syy[0] * self.normal[1],
                    ]
                )
                nodal_forces += weight * jacobian * np.outer(N, traction)

            for i, node in enumerate(geom):
                current = node.GetSolutionStepValue(SMA.POINT_LOAD)
                node.SetSolutionStepValue(
                    SMA.POINT_LOAD,
                    0,
                    [current[0] + nodal_forces[i, 0], current[1] + nodal_forces[i, 1], 0.0],
                )

                if node.Id not in ConsistentTractionProcess._nodes_with_point_load_condition:
                    ConsistentTractionProcess._nodes_with_point_load_condition.add(node.Id)
                    max_condition_id += 1
                    root_model_part.CreateNewCondition(
                        "PointLoadCondition2D1N", max_condition_id, [node.Id], properties
                    )
