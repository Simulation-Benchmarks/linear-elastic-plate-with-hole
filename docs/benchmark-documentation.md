# Infinite linear elastic plate with hole

## Problem description

We consider the case of an infinite plate with a circular hole with radius $a$ in the center. The plate is subjected to uniform tensile load $p$ at infinity. The analytical solution for the stress field has been derived by Kirsch in 1898 [@Kirsch1898].
<!-- include an svg picture here-->
![Infinite linear elastic plate with hole](plate-with-hole.svg)

The solution is given in polar stress components of the Cauchy stress tensor $\boldsymbol \sigma$ at a point with polar coordinates $(r,\theta)\in\mathbb R_+ \times \mathbb R$. Assume that the infinite plate is loaded in $x$-direction with load $p$, then the polar stress components are given by

$$
    \begin{aligned}
        \sigma_{rr}(r,\theta) &= \frac{p}{2}\left(1-\frac{a^2}{r^2}\right)+\frac{p}{2}\left(1-\frac{a^2}{r^2}\right)\left(1-\frac{3a^2}{r^2}\right)\cos(2\theta)\\
        \sigma_{\theta\theta}(r,\theta) &=\frac{p}{2}\left(1+\frac{a^2}{r^2}\right) - \frac{p}{2}\left(1+\frac{3a^4}{r^4}\right)\cos(2\theta)\\
        \sigma_{r\theta}(r,\theta) &= -\frac{p}{2}\left(1-\frac{a^2}{r^2}\right)\left(1+\frac{3a^2}{r^2}\right)\sin(2\theta)
    \end{aligned}
$$

In order to write the stresses in a cartesian coordiante system, they need to be rotated by $\theta$, which results in

$$
    \begin{aligned}
        \sigma_{xx} (r,\theta) &=  \frac{3 a^{4} p \cos{\left(4 \theta \right)}}{2 r^{4}} - \frac{a^{2} p \left(1.5 \cos{\left(2 \theta \right)} + \cos{\left(4 \theta \right)}\right)}{r^{2}} + p \\
        \sigma_{yy} (r,\theta)&= - \frac{3 a^{4} p \cos{\left(4 \theta \right)}}{2 r^{4}} - \frac{a^{2} p \left(\frac{\cos{\left(2 \theta \right)}}{2} - \cos{\left(4 \theta \right)}\right)}{r^{2}}\\
        \sigma_{xy} (r,\theta) &= \frac{3 a^{4} p \sin{\left(4 \theta \right)}}{2 r^{4}} - \frac{a^{2} p \left(\frac{\sin{\left(2 \theta \right)}}{2} + \sin{\left(4 \theta \right)}\right)}{r^{2}}
    \end{aligned}
$$

with the full stress tensor solution given by

$$
\boldsymbol\sigma_\mathrm{analytical} (r,\theta)= \begin{bmatrix} \sigma_{xx}(r,\theta) & \sigma_{xy}(r,\theta)\\\ \sigma_{xy}(r,\theta) & \sigma_{yy}(r,\theta) \end{bmatrix}.
$$

or for a cartesion point $(x,y)\in \mathbb R_+^2$:

$$
\boldsymbol\sigma_\mathrm{analytical} (x,y)=\boldsymbol\sigma_\mathrm{analytical} \left(\sqrt{x^2 + y^2},\arccos\frac{x}{\sqrt{x^2+y^2}}\right). 
$$

In order to transform this into a practical benchmark, we consider a rectangular subdomain
of the infinite plate around the hole. The boundary conditions of the subdomain are determined
from the analytical solution. The example is further reduced by only simulating one quarter
of the rectangular domain with length $l$ and assuming symmetry conditions at the edges. Let 

$$
\Omega =[0,l]^2 \setminus \lbrace (x,y) \mid \sqrt{x^2+y^2}<a \rbrace
$$ 

be the domain of the benchmark example and

$$
\begin{aligned}
\Gamma_\mathrm{D_1} &= \lbrace (x,y)\in \partial\Omega | y=0\rbrace \\
\Gamma_\mathrm{D_2} &= \lbrace (x,y)\in \partial\Omega | x=0\rbrace \\
\Gamma_\mathrm{N} &= \lbrace (x,y)\in \partial\Omega | x=l \lor y=l \rbrace
\end{aligned}
$$

then the PDE with the displacement $\boldsymbol u$ as solution variable is given by

$$
\begin{aligned}
\mathrm{div}\boldsymbol{\sigma}(\boldsymbol{\varepsilon}(\boldsymbol{u})) &= 0 &\quad \text{ on } \Omega & \\
\boldsymbol{\varepsilon}(\boldsymbol u) &= \frac{1}{2}\left(\nabla \boldsymbol u + (\nabla\boldsymbol u)^\top\right) &&\text{Infinitesimal strain}\\
\boldsymbol{\sigma}(\boldsymbol{\varepsilon}) &= \frac{E}{1-\nu^2}\left((1-\nu)\boldsymbol{\varepsilon} + \nu \mathrm{tr}\boldsymbol{\varepsilon}\boldsymbol I_2\right) && \text{Plane stress law}\\
\boldsymbol u_y &=0 & \text{ on } \Gamma_\mathrm{D_1}& \text{ Dirichlet BC}\\
\boldsymbol u_x &=0 & \text{ on } \Gamma_\mathrm{D_2}& \text{ Dirichlet BC}\\
\boldsymbol t &= \tilde{\boldsymbol{t}} & \text{ on } \Gamma_\mathrm{N} & \text{ Neumann BC}\\
\end{aligned}
$$

with the material parameters $E,\nu$ -- the Youngs modulus and Poisson ratio. The traction $\boldsymbol t$ is the Cauchy stress tensor multiplied by the normal vector on the boundary $\boldsymbol \sigma \cdot \boldsymbol n$. Prescribing a value $\tilde{\boldsymbol t}$ on a subset of the boundary $\partial\Omega$ is referred to as a Neumann boundary condition in computational mechanics. In this specific example, 

$$
\tilde{\boldsymbol t} =\boldsymbol\sigma_\mathrm{analytical} \cdot \boldsymbol{n}.
$$

## Weak formulation and numerical solution

In the weak formulation of the problem, we want to find $\boldsymbol u$ such that

$$
B(\boldsymbol u,\boldsymbol v) = f(\boldsymbol{v}) \quad \forall \boldsymbol v 
$$

with a test function $\boldsymbol{v}$ and 

$$
\begin{aligned}
B(\boldsymbol u,\boldsymbol v) &= \int_{\Omega} \boldsymbol\varepsilon(\boldsymbol{v}) : \boldsymbol{\sigma}(\boldsymbol{\varepsilon}(\boldsymbol{u})) \mathrm{d}{\boldsymbol{x}} \\
    f(\boldsymbol v)&=\int_{\Gamma_{\mathrm{N}}} {\boldsymbol{t}}\cdot\boldsymbol{v}\mathrm{d}{\boldsymbol{s}}.
\end{aligned}
$$


In order to solve the weak formulation, the Finite Element Method (FEM) can be used. This method discretizes the domain $\Omega$ into so called finite elements that can for example be triangles or quadrilaterals in 2D. On these elements, ansatz functions are defined such that they are continuous on the boundaries between elements. These functions form a basis for the solution space for an approximate solution $\boldsymbol{u}_h$ of the problem.

## Input Parameters

| Parameter    | Description                     |
| ------------ | ------------------------------  |
| $radius$[m]   | Radius of the hole.             |
| $length$[m]   | Length of the benchmark domain. |
| $youngs\_modulus$[Pa]  | Youngs modulus.                 |
| $poissons\_ratio$  | Poisson ratio.                  |
| $load$[Pa]  | Load at infinity.               |
| $element\_size$[m]   | Element size.                        |
| $isoparametric\_element\_degree$ | Degree of shape functions used to model the element's geometry and the solution field. |
| $cell\_type$  | Element shape ("triangle" or "quadrilateral").           |
| $element\_category$  | "lagrange" (default) or "serendipity".         |

## Output Metrics

| Metric | Description |                     
| ------------ | ------------------------------  |
| $number\_of\_dofs$[-] | Total degrees of freedom in the FE mesh. |
| $max\_von\_mises\_stress$[Pa] | FE model max Von-Mises stress output. |
| $l2\_error\_displacement$[m] | $L_2$ norm of the error between the FE and the analytical displacements. $\Vert \boldsymbol{f}\Vert_{L_2} := \sqrt{\int_\Omega \|\boldsymbol{f}(\boldsymbol{x})\|^2 \mathrm{d} \boldsymbol{x}}$ |
| $max\_displacement\_error$[m] | Error between the FE and the analytical displacements computed at the nodes of the mesh. |
| $reaction\_force\_left\_boundary\_x$[N]  | FE model reaction force along the X-direction at the left boundary, computed from the residual as defined below.|
| $reaction\_force\_left\_boundary\_y$[N]  | FE model reaction force along the Y-direction at the left boundary, computed from the residual as defined below.|
| $displacement\_top\_right\_corner$[m] | FE model displacements at the top-right corner.|

### Reaction forces

The reaction forces are the forces that the supports exert on the plate. They are computed from the residual of the discrete problem at the nodes of the left boundary, not by integrating the traction $\boldsymbol\sigma(\boldsymbol u_h)\cdot\boldsymbol n$ of the discrete solution along the boundary. With the shape function $\varphi_i$ of node $i$ and the unit vectors $\boldsymbol e_x, \boldsymbol e_y$,

$$
\begin{aligned}
reaction\_force\_left\_boundary\_x &= \sum_{i \in I} \Big( B(\boldsymbol u_h, \varphi_i \boldsymbol e_x) - f(\varphi_i \boldsymbol e_x) \Big), \\
reaction\_force\_left\_boundary\_y &= \sum_{i \in I} \Big( B(\boldsymbol u_h, \varphi_i \boldsymbol e_y) - f(\varphi_i \boldsymbol e_y) \Big),
\end{aligned}
$$

where $I$ is the set of nodes on the left boundary $\Gamma_\mathrm{D_2}$ and $f$ includes every Neumann load acting on these nodes, such as the load on the top boundary at the corner $(0, l)$. Every tool reports the components of the force acting on the plate, so the $x$-component is negative.

The residual is zero at all unconstrained degrees of freedom. Only $\boldsymbol u_x$ is constrained on $\Gamma_\mathrm{D_2}$, so the $y$-component vanishes. Since $\sum_i \varphi_i = 1$, the sum over all nodes of $B(\boldsymbol u_h, \varphi_i \boldsymbol e_x)$ vanishes, so the $x$-component is equal to the negative total $x$-load applied on $\Gamma_\mathrm{N}$ by the discrete load vector, and its error only measures how accurately a tool integrates the Neumann load. The analytical value is

$$
reaction\_force\_left\_boundary\_x = -\int_a^l \sigma_{xx}(0, y)\,\mathrm{d}y = -p\left( l - a + \frac{a}{2}\left(1 - \frac{a}{l}\right) + \frac{a}{2}\left(1 - \frac{a^3}{l^3}\right) \right).
$$
