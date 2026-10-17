/* ------------------------------------------------------------------------
 *
 * SPDX-License-Identifier: MIT
 * Copyright (C) 2026 Jan Philipp Thiele
 *
 * This file is adopted from step-3.cc and step-3-simplex.cc, which are part of the deal.II library
 *
 * ------------------------------------------------------------------------
 */
#include <boost/program_options.hpp>

#include <deal.II/grid/tria.h>
#include <deal.II/dofs/dof_handler.h>
#include <deal.II/grid/grid_tools.h>
#include <deal.II/grid/manifold_lib.h>

#include <deal.II/fe/fe_q.h>
#include <deal.II/fe/fe_simplex_p.h>
#include <deal.II/fe/mapping_p1.h>

#include <deal.II/dofs/dof_tools.h>
#include <deal.II/dofs/dof_renumbering.h>

#include <deal.II/grid/grid_in.h>

#include <deal.II/fe/component_mask.h>
#include <deal.II/fe/fe_values.h>
#include <deal.II/fe/fe_system.h>
#include <deal.II/base/quadrature_lib.h>

#include <deal.II/base/function.h>
#include <deal.II/base/tensor_function.h>
#include <deal.II/base/parameter_handler.h>
#include <deal.II/numerics/vector_tools.h>
#include <deal.II/numerics/matrix_tools.h>

#include <deal.II/lac/vector.h>
#include <deal.II/lac/full_matrix.h>
#include <deal.II/lac/sparse_matrix.h>  
#include <deal.II/lac/sparse_direct.h>
#include <deal.II/lac/dynamic_sparsity_pattern.h>
#include <deal.II/lac/solver_cg.h>
#include <deal.II/lac/precondition.h>


#include <deal.II/numerics/data_out.h>
#include <exception>
#include <fstream>
#include <iostream>

using namespace dealii;

class BenchmarkFiles{
  public: 
    BenchmarkFiles(std::string in_mesh, std::string out_metrics)
    : in_mesh(in_mesh)
    , out_metrics(out_metrics)
    {}

  std::string in_mesh;
  std::string out_metrics;
};

class Parameters
{
  public:
    Parameters();

    static void declare_parameters(ParameterHandler &prm);
    void get_parameters(ParameterHandler &prm);
    void print_parameters();

    std::string configuration;
    double radius;
    double length;
    double load;
    double youngs_modulus;
    double poissons_ratio;
    int degree;
    std::string cell_type;
};

Parameters::Parameters()
  : configuration("5")
  , radius(0.33)
  , length(1.0)
  , load(100000000.0)
  , youngs_modulus(2100000000.0)
  , poissons_ratio(0.3)
  , degree(1)
  , cell_type("quadrilateral")
{}

void Parameters::declare_parameters(
  ParameterHandler &prm
)
{
  prm.declare_entry("configuration", 
                    "2",
                    Patterns::Anything(),
                    "id of the configuration to run");
  prm.declare_entry("radius[m]",
                    "0.33",
                    Patterns::Double(),
                    "radius of the hole");
  prm.declare_entry("length[m]",
                    "1.0",
                    Patterns::Double(),
                    "length of the plate");
  prm.declare_entry("load[Pa]",
                    "100000000.0",
                    Patterns::Double(),
                    "load force");
  prm.declare_entry("youngs_modulus[Pa]",
                    "2100000000.0",
                    Patterns::Double(),
                    "");                  
  prm.declare_entry("poissons_ratio",
                    "0.3",
                    Patterns::Double(),
                    "");
  prm.declare_entry("element_size[m]",
                    "0.1",
                    Patterns::Double(),
                    "maximum size of an element");
  prm.declare_entry("isoparametric_element_degree",
                    "1",
                    Patterns::Integer(),
                    "Degree of the element");
  prm.declare_entry("cell_type", 
                    "triangle",
                    Patterns::Anything(),
                    "geometry of the elements");
}

void Parameters::get_parameters(
  ParameterHandler &prm)
{
  configuration = prm.get("configuration");
  radius = prm.get_double("radius[m]");
  length = prm.get_double("length[m]");
  load = prm.get_double("load[Pa]");
  youngs_modulus = prm.get_double("youngs_modulus[Pa]");
  poissons_ratio = prm.get_double("poissons_ratio");
  degree = prm.get_integer("isoparametric_element_degree");
  cell_type = prm.get("cell_type");
}

void Parameters::print_parameters(){
  std::cout 
    << "configuration: " << configuration 
    << "\nradius: " << radius
    << "\nlength: " << length
    << "\nload: " << load
    << "\nyoungs_modulus: " << youngs_modulus
    << "\npoissons_ratio: " << poissons_ratio
    << std::endl;
}

class SigmaExact : public TensorFunction<1,2,double>
{
  public: 
    SigmaExact(Parameters& params)
      : TensorFunction<1,2,double>()
      , params(params)
    {}
    
    virtual Tensor<2,2> value(const Point<2>& p){
      double x = p[0];
      double y = p[1];
      double r = std::sqrt(x*x+y*y);
      double theta = std::atan2(y,x);
      double c2t = std::cos(2*theta);
      double c4t = std::cos(4*theta);
      double s2t = std::sin(2*theta);
      double s4t = std::sin(4*theta);
      double a = params.radius;
      double T = params.load;
      double fac1 = a*a/(r*r);
      double fac2 = T*1.5*fac1*fac1;

      Tensor<2,2> result;
      result[0][0] = T - T*fac1 * (1.5 * c2t + c4t) + fac2 * c4t;
      result[1][1] = -T*fac1 * (0.5 * c2t - c4t) - fac2 * c4t;
      result[0][1] = -T*fac1 * (0.5 * s2t + s4t) + fac2 * s4t;
      result[1][0] = result[0][1];
      return result;
    }

    Parameters& params;
};

class Solution : public Function<2>
{
  public: 
    Solution(Parameters& params)
    : Function<2>(2)
    , a(params.radius)
    , T(params.load)
    , E(params.youngs_modulus)
    , nu(params.poissons_ratio)
    , Ta_8mu(T * a * (1.0 + nu) / (4.0 * E))
    , k((3.0-nu) / (1.0 + nu))
    {}
    virtual double value(const Point<2> &p,
                         const unsigned int component = 0) const override;

    virtual void vector_value(const Point<2> &p,
                              Vector<double> &values) const override;

    double a;
    double T;
    double E;
    double nu;
    double Ta_8mu;
    double k;
};

double Solution::value(const Point<2> &p, const unsigned int component) const
{
  Vector<double> values(2);
  vector_value(p,values);
  return values[component];
}

void Solution::vector_value(const Point<2> &p, Vector<double> &values) const
{
  double x = p[0];
  double y = p[1];
  double r = std::sqrt(x*x+y*y);
  double theta = std::atan2(y,x);
  double ct = std::cos(theta);
  double c3t = std::cos(3.0*theta);
  double st = std::sin(theta);
  double s3t = std::sin(3.0*theta);
  double fac = 2.0*std::pow(a/r,3);

  values[0] = Ta_8mu *(
    (r/a) * (k+1.0) * ct
    + 2.0 * (a/r) * ((1.0 + k) * ct + c3t)
    - fac * c3t
  );
  values[1] = Ta_8mu *(
    (r/a) * (k-3.0) * st
    + 2.0 * (a/r) * ((1.0 - k) * st + s3t)
    - fac * s3t
  );
}

class Metrics{
  public:

    Metrics()
    : ndofs(0)
    , max_von_mises(0)
    , L2_error(0)
    , max_displacement(0)
    , reaction_force_left_boundary(2)
    , displacement_top_right_corner(2)
    {}

    void print_to_json();

    unsigned int ndofs;
    double max_von_mises;
    double L2_error;
    double max_displacement;
    Vector<double> reaction_force_left_boundary;
    Vector<double> displacement_top_right_corner;
};

void Metrics::print_to_json(){
  //Todo: open metrics.json file and print to it
  std::ofstream metricsfile("metrics.json");

  // std::cout 
  metricsfile
  << std::setprecision (15) << std::scientific
  << "{\n"
  << "  \"number_of_dofs[-]\": " << ndofs << ",\n"
  << "  \"max_von_mises_stress[Pa]\": " << max_von_mises << ",\n"
  << "  \"l2_error_displacement[m]\": " << L2_error << ",\n"
  << "  \"max_displacement_error[m]\": " << max_displacement << ",\n"
  << "  \"reaction_force_left_boundary_x[N]\": " << reaction_force_left_boundary[0] << ",\n"
  << "  \"reaction_force_left_boundary_y[N]\": " << reaction_force_left_boundary[1] << ",\n"
  << "  \"displacement_top_right_corner[m]\": [\n" 
  << "    " << displacement_top_right_corner[0] << ",\n" 
  << "    " << displacement_top_right_corner[1] << "\n"
  << "  ]\n"
  << "}" << std::endl;

  metricsfile.close();
}

class KirschPlate
{
public:
  KirschPlate(Parameters& param);

  void run();


private:
  void make_grid();
  void setup_system(const FESystem<2>&);
  void assemble_system(const FESystem<2>&, const Quadrature<2>&, const Quadrature<1>&, const Mapping<2>&);
  void assemble_vonMises_stresses(const FESystem<2>&, const Quadrature<2>&, const Mapping<2>&);
  void apply_dirichlet_bc();
  void solve();
  void calculate_metrics(const FESystem<2>&, const Quadrature<2>&,const Mapping<2>&);
  void output_results() const;
  void sigma(const Tensor<2,2>& grad_u, Tensor<2,2>& sig);

  Triangulation<2> triangulation;
  const FESystem<2> fe_quad;
  const FESystem<2> fe_tria;
  DoFHandler<2> dof_handler;

  SparsityPattern      sparsity_pattern;
  SparseMatrix<double> system_matrix;

  Vector<double> solution;
  Vector<double> exact_solution;
  Vector<double> system_rhs;
  Vector<double> vonMises_stresses;

  ComponentMask ux_mask;
  ComponentMask uy_mask;

  Tensor<2,2> Id;

  Parameters& params;
  std::string meshfile;
  Metrics metrics;
};

KirschPlate::KirschPlate(Parameters& params)
  : fe_quad(FE_Q<2>(params.degree),2)
  , fe_tria(FE_SimplexP<2>(params.degree),2)
  , dof_handler(triangulation)
  , params(params)
  , metrics()
{}


void KirschPlate::make_grid() 
{
  GridIn<2>(triangulation).read("mesh.msh");
  GridTools::map_boundary_to_manifold_ids({5},{5},triangulation);
  Point<2> p(0.0,0.0);
  SphericalManifold<2> circle_manifold(p);
  triangulation.set_manifold(5,circle_manifold);
}

void KirschPlate::setup_system(const FESystem<2>& fe)
{
  dof_handler.distribute_dofs(fe);
  DoFRenumbering::component_wise(dof_handler);
  std::cout << "Number of degrees of freedom: " << dof_handler.n_dofs()
            << std::endl;
            
  DynamicSparsityPattern dsp(dof_handler.n_dofs());
  DoFTools::make_sparsity_pattern(dof_handler, dsp);
  sparsity_pattern.copy_from(dsp);

  system_matrix.reinit(sparsity_pattern);

  solution.reinit(dof_handler.n_dofs());
  system_rhs.reinit(dof_handler.n_dofs());
  exact_solution.reinit(dof_handler.n_dofs());

  vonMises_stresses.reinit(triangulation.n_active_cells());

  VectorTools::interpolate(dof_handler,Solution(params),exact_solution);

  Id[0][0] = 1.0;
  Id[1][1] = 1.0;
  Id[0][1] = 0.0;
  Id[1][0] = 0.0;

  auto xmask = std::vector({true,false});
  auto ymask = std::vector({false,true});
  ux_mask = ComponentMask(xmask);
  uy_mask = ComponentMask(ymask);
}

void KirschPlate::sigma(const Tensor<2,2> &grad_u, Tensor<2,2> &sig)
{
  double nu = params.poissons_ratio;
  double E = params.youngs_modulus;
  double factor = E/(1-nu*nu);
  sig = ((1.0-nu)*grad_u+nu*trace(grad_u)*Id)*factor;
}


void KirschPlate::assemble_system(const FESystem<2>& fe,const Quadrature<2>& quadrature_formula, const Quadrature<1>& face_quadrature_formula, const Mapping<2>& mapping)
{ 
  system_matrix=0.;
  system_rhs=0.;
  FEValues<2> fe_values(mapping, fe,
                        quadrature_formula,
                        update_gradients | update_JxW_values);
  
  FEFaceValues<2> fe_face_values(mapping, fe,
                                 face_quadrature_formula,
                                 update_values | update_quadrature_points | update_JxW_values | update_normal_vectors);

  const unsigned int dofs_per_cell = fe.n_dofs_per_cell();

  FullMatrix<double> cell_matrix(dofs_per_cell, dofs_per_cell);
  Vector<double>     cell_rhs(dofs_per_cell);

  std::vector<types::global_dof_index> local_dof_indices(dofs_per_cell);

  FEValuesExtractors::Vector displacements(0);

  Tensor<2,2> grad_u;
  Tensor<2,2> sig;
  SigmaExact sigma_ex= SigmaExact(params);
  for (const auto &cell : dof_handler.active_cell_iterators())
    {
      
      fe_values.reinit(cell);

      cell_matrix = 0;
      cell_rhs    = 0;

      for (const unsigned int q_index : fe_values.quadrature_point_indices())
      {

          for (const unsigned int i : fe_values.dof_indices())
          {
              grad_u = fe_values[displacements].gradient(i,q_index);
              grad_u[1][0] = (grad_u[1][0]+grad_u[0][1])*0.5;
              grad_u[0][1] = grad_u[1][0];
              sigma(grad_u,sig);

            for (const unsigned int j : fe_values.dof_indices())
            {
              cell_matrix(j, i) +=
                scalar_product(sig,fe_values[displacements].gradient(j,q_index))
                * fe_values.JxW(q_index);
            }
          }
      }

      for (const auto & face : cell -> face_iterators())
        if (face->at_boundary()) 
          if (face->boundary_id() >= 3)
          {
            fe_face_values.reinit(cell,face);
            for (unsigned int q_index : fe_face_values.quadrature_point_indices()){
              const auto traction = sigma_ex.value(fe_face_values.quadrature_point(q_index)) *
              fe_face_values.normal_vector(q_index);
  
              for (unsigned int i : fe_face_values.dof_indices())
                cell_rhs(i) += fe_face_values[displacements].value(i,q_index)*traction*fe_face_values.JxW(q_index);
           
            }
      } 
      
      cell->get_dof_indices(local_dof_indices);

      for (const unsigned int i : fe_values.dof_indices())
        for (const unsigned int j : fe_values.dof_indices())
          system_matrix.add(local_dof_indices[i],
                            local_dof_indices[j],
                            cell_matrix(i, j));

      for (const unsigned int i : fe_values.dof_indices())
        system_rhs(local_dof_indices[i]) += cell_rhs(i);
    }
}

void KirschPlate::apply_dirichlet_bc()
{

  std::map<types::global_dof_index, double> boundary_values;

  VectorTools::interpolate_boundary_values(dof_handler,
                                           types::boundary_id(1),
                                           Functions::ZeroFunction<2>(2),
                                           boundary_values,
                                           ux_mask);
  VectorTools::interpolate_boundary_values(dof_handler,
                                           types::boundary_id(2),
                                           Functions::ZeroFunction<2>(2),
                                           boundary_values,
                                           uy_mask);
                                           
  MatrixTools::apply_boundary_values(boundary_values,
                                     system_matrix,
                                     solution,
                                     system_rhs);
}

void KirschPlate::assemble_vonMises_stresses(const FESystem<2>& fe,const Quadrature<2>& quadrature_formula, const Mapping<2>& mapping)
{ 
  vonMises_stresses = 0.;
  
  FEValues<2> fe_values(mapping,fe,
                        quadrature_formula,
                        update_gradients | update_JxW_values);


  const unsigned int dofs_per_cell = fe.n_dofs_per_cell();

  std::vector<types::global_dof_index> local_dof_indices(dofs_per_cell);

  FEValuesExtractors::Vector displacements(0);

  std::vector<Tensor<2,2>> grad_u(quadrature_formula.size());
  Tensor<2,2> sig;
  Tensor<2,2> s;
  double factor=0.;
  double p = 0.;
  for (const auto &cell : dof_handler.active_cell_iterators())
    {
      
      fe_values.reinit(cell);

      fe_values[displacements].get_function_gradients(solution, grad_u);
      factor = std::sqrt(1.5)/cell->measure();

      for (const unsigned int q_index : fe_values.quadrature_point_indices())
      {
        grad_u[q_index][1][0] = (grad_u[q_index][1][0]+grad_u[q_index][0][1])*0.5;
        grad_u[q_index][0][1] = grad_u[q_index][1][0];
        sigma(grad_u[q_index],sig);
        p = trace(sig)/3.0;
        s = sig - p*Id;
        vonMises_stresses[cell->global_active_cell_index()]
          += std::sqrt(scalar_product(s,s)+p*p)*factor*fe_values.JxW(q_index);
      }
      
    }
    metrics.max_von_mises = vonMises_stresses.linfty_norm();
}

void KirschPlate::solve()
{
  SparseDirectUMFPACK solver_umfpack;
  solution = system_rhs;
  solver_umfpack.solve(system_matrix,solution);
}

void KirschPlate::calculate_metrics(const FESystem<2>& fe,const Quadrature<2>& quadrature_formula, const Mapping<2>& mapping)
{
  metrics.ndofs = dof_handler.n_dofs();

  Vector <double> difference_per_cell(triangulation.n_active_cells());
  VectorTools::integrate_difference(mapping,
                                    dof_handler,
                                    solution,
                                    Solution(params),
                                    difference_per_cell,
                                    quadrature_formula,
                                    VectorTools::L2_norm);

  metrics.L2_error = 
    VectorTools::compute_global_error(triangulation,
                                      difference_per_cell,
                                      VectorTools::L2_norm);

  Point<2> top_right_corner(params.length,params.length);
  VectorTools::point_value(mapping,
                           dof_handler,
                           solution,
                           top_right_corner,
                           metrics.displacement_top_right_corner
                           );

  assemble_vonMises_stresses(fe, quadrature_formula,mapping);
  
  Vector<double> displacement_errors=exact_solution;
  displacement_errors-= solution;
  metrics.max_displacement = displacement_errors.linfty_norm();

  Vector<double> residual;
  residual.reinit(dof_handler.n_dofs());
  system_matrix.vmult(residual,solution);
  residual-=system_rhs;
  
  IndexSet left_x_ids = DoFTools::extract_boundary_dofs(dof_handler,ux_mask,{1});
  IndexSet left_y_ids = DoFTools::extract_boundary_dofs(dof_handler,uy_mask,{1});

  for (auto i : left_x_ids){
    metrics.reaction_force_left_boundary[0]+= residual[i];
  }
  for (auto i : left_y_ids){
    metrics.reaction_force_left_boundary[1]+= residual[i];
  }

  metrics.print_to_json();
}

void KirschPlate::output_results() const
{
  
  std::vector<std::string> field_names;
  std::vector<std::string> mag_names;
  std::vector<std::string> ex_names;
  std::vector<DataComponentInterpretation::DataComponentInterpretation> dci;

  field_names.push_back("u_x");
  field_names.push_back("u_y");
  mag_names.push_back("u_mag");
  mag_names.push_back("u_ex_mag");
  ex_names.push_back("u_ex_x");
  ex_names.push_back("u_ex_y");
  dci.push_back(DataComponentInterpretation::component_is_scalar);
  dci.push_back(DataComponentInterpretation::component_is_scalar);


  unsigned int n_dofs_x = dof_handler.n_dofs()/2;
  Vector<double> u_mag;
  u_mag.reinit(n_dofs_x*2);
  for (unsigned int i = 0 ; i < n_dofs_x ; i++){
    u_mag[i] = std::sqrt(solution[i]*solution[i]+solution[i+n_dofs_x]*solution[i+n_dofs_x]);
  }

  DataOut<2> data_out;
  data_out.attach_dof_handler(dof_handler);
  data_out.add_data_vector(solution, field_names, DataOut<2>::type_dof_data,dci);
  data_out.add_data_vector(u_mag,mag_names,DataOut<2>::type_dof_data,dci);
  data_out.add_data_vector(exact_solution,ex_names,DataOut<2>::type_dof_data,dci);

  data_out.build_patches();

  const std::string filename = "solution.vtk";
  std::ofstream     output(filename);
  data_out.write_vtk(output);
}

void KirschPlate::run()
{
  make_grid();
  if (params.cell_type == "triangle"){
    setup_system(fe_tria);
    const QGaussSimplex<2> quad(fe_tria.degree+2);
    const QGaussSimplex<1> face_quad(fe_tria.degree +1);
    assemble_system(fe_tria, quad,face_quad,MappingP1<2>());
    apply_dirichlet_bc();
    solve();
    // We need the equation system without Dirichlet BC for traction forces
    assemble_system(fe_tria, quad,face_quad,MappingP1<2>());
    calculate_metrics(fe_tria,quad,MappingP1<2>());
  } else {
    setup_system(fe_quad);
    const QGauss<2> quad(fe_quad.degree+2);
    const QGauss<1> face_quad(fe_quad.degree +1);
    unsigned int mapping_degree = 1;
    if (fe_quad.degree > 1 ){
      mapping_degree = fe_quad.degree*4;
    }
    assemble_system(fe_quad, quad,face_quad,MappingQ<2>(mapping_degree));
    apply_dirichlet_bc();
    solve();
    // We need the equation system without Dirichlet BC for traction forces
    assemble_system(fe_quad, quad,face_quad,MappingQ<2>(mapping_degree));
    calculate_metrics(fe_quad,quad,MappingQ<2>(mapping_degree));
  }
  output_results();
}


int main(int argc, char** argv)
{
  try {
    if (argc < 2)
    {
      std::cerr << "\n\n----------------------------------------------------"
                << "\nMissing parameter file"
                << "\nUsage: ./kirsch_plate <parameterfile>.json"
                << "\n----------------------------------------------------"
                << std::endl;
    }
    std::string configfile = argv[1];

    Parameters parameters;
    ParameterHandler prm;
    parameters.declare_parameters(prm);
    prm.parse_input(configfile,"",true);
    parameters.get_parameters(prm);
    parameters.print_parameters();
    KirschPlate benchmark_problem(parameters);
    benchmark_problem.run();
  }
  catch (std::exception &exc)
  {
    std::cerr << "\n\n----------------------------------------------------"
              << "\nException on processing: \n" << std::endl
              << exc.what() 
              << "\nAborting!"
              << "\n----------------------------------------------------"
              << std::endl;

    return 1;
  }
  catch (...)
  {
    std::cerr << "\n\n----------------------------------------------------"
              << "\nUnknown exception!"
              << "\nAborting!"
              << "\n----------------------------------------------------"
              << std::endl;
    return 1;
  }
  
  return 0;
}
