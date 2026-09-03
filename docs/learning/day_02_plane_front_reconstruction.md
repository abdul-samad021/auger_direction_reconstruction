# Day 2 — From station times to a physical shower direction

## Purpose

This module develops the mathematical reconstruction that follows the Day 1
moving-plane geometry. The goal is not merely to obtain an angle from a solver. It
is to understand how every selected station contributes to an uncertainty-aware,
physically constrained estimate of the shower direction.

By the end of this module, we should be able to explain:

- how the moving-plane equation predicts a station's signal-start time;
- what the event-time offset means and why coordinate centring removes it;
- why ordinary residuals lead to least squares;
- why Auger's `dt` values lead to weighted least squares;
- how all station equations form a design matrix;
- why we solve an overdetermined system without explicitly inverting a matrix;
- why the raw linear solution need not be a physical unit vector;
- how a constrained fit produces zenith and azimuth;
- how propagation direction differs from sky-arrival direction.

The final implementation will use selected station positions, start times, and
timing uncertainties only. Auger's published direction remains quarantined until
our prediction has been recorded.

## 1. The reconstruction problem

For selected station $i$, the released measurements include

$$
\mathbf r_i=(x_i,y_i,z_i)
$$

and an observed signal-start time

$$
t_i^{\mathrm{obs}}.
$$

We want to infer the downward propagation direction

$$
\mathbf u=(u_x,u_y,u_z),
$$

subject to

$$
\lVert\mathbf u\rVert=1,
\qquad
u_z<0
$$

when the positive $z$-axis points upward. The opposite vector

$$
\boxed{\mathbf a=-\mathbf u}
$$

points back toward the apparent source direction in the sky.

From the moving-plane equation derived on Day 1,

$$
\mathbf u\cdot\mathbf r-ct=K,
$$

the predicted arrival time at station $i$ is

$$
\boxed{
t_i^{\mathrm{pred}}
=t_0+\frac{\mathbf u\cdot\mathbf r_i}{c}
}.
$$

Here

$$
c=0.299792458\ \mathrm{m/ns}
$$

when station positions are in metres and times are in nanoseconds.

### What $t_0$ means

At the coordinate origin, $\mathbf r=\mathbf 0$, so

$$
t=t_0+\frac{\mathbf u\cdot\mathbf 0}{c}=t_0.
$$

Therefore, $t_0$ is the time at which the modelled plane passes through the
chosen coordinate origin. It is a nuisance parameter rather than a direction.

If the origin moves to $\mathbf s$, the new coordinates are

$$
\mathbf r_i'=\mathbf r_i-\mathbf s,
$$

so $\mathbf r_i=\mathbf r_i'+\mathbf s$. Substitution gives

$$
t_i
=t_0+\frac{\mathbf u\cdot(\mathbf r_i'+\mathbf s)}{c}
=\left(t_0+\frac{\mathbf u\cdot\mathbf s}{c}\right)
+\frac{\mathbf u\cdot\mathbf r_i'}{c}.
$$

Thus,

$$
\boxed{
t_0'=t_0+\frac{\mathbf u\cdot\mathbf s}{c}
}.
$$

Changing the origin changes the time at which the front passes that reference
point. It does not physically rotate the shower, so $\mathbf u$ does not change.

For example, moving the origin $300$ m along a direction with $u_x=0.5$ changes
the reference time by approximately

$$
\Delta t_0
=\frac{(0.5)(300\ \mathrm m)}{0.3\ \mathrm{m/ns}}
\approx500\ \mathrm{ns}.
$$

### Relative times remove the common offset

For stations $i$ and $j$,

$$
t_i=t_0+\frac{\mathbf u\cdot\mathbf r_i}{c},
$$

$$
t_j=t_0+\frac{\mathbf u\cdot\mathbf r_j}{c}.
$$

Subtracting them gives

$$
\boxed{
c(t_i-t_j)=\mathbf u\cdot(\mathbf r_i-\mathbf r_j)
}.
$$

The common $t_0$ cancels. The timing pattern, rather than the arbitrary absolute
timestamp, contains the directional information.

## 2. A three-station numerical example

Consider three stations at the same altitude:

$$
\mathbf r_A=(0,0,0)\ \mathrm m,
$$

$$
\mathbf r_B=(300,0,0)\ \mathrm m,
$$

$$
\mathbf r_C=(0,300,0)\ \mathrm m.
$$

Suppose their arrival times are

$$
t_A=0\ \mathrm{ns},
\qquad
t_B=500\ \mathrm{ns},
\qquad
t_C=600\ \mathrm{ns}.
$$

Station $A$ is at the chosen origin, so $t_0=0$. For station $B$,

$$
500=\frac{300u_x}{c},
$$

and therefore

$$
u_x=\frac{c(500)}{300}\approx0.500.
$$

Similarly,

$$
600=\frac{300u_y}{c},
$$

so

$$
u_y\approx0.600.
$$

The unit-vector condition requires

$$
u_x^2+u_y^2+u_z^2=1.
$$

Consequently,

$$
u_z
=\pm\sqrt{1-0.500^2-0.600^2}
=\pm\sqrt{0.39}
\approx\pm0.625.
$$

The flat station timing cannot distinguish upward from downward propagation. The
physical shower travels downward, so we choose

$$
\boxed{
\mathbf u\approx(0.500,0.600,-0.625)
}.
$$

The sky-arrival vector is

$$
\boxed{
\mathbf a=-\mathbf u\approx(-0.500,-0.600,0.625)
}.
$$

Three non-collinear stations are the conceptual minimum for two direction degrees
of freedom plus one time offset. Real measurements are noisy, so a many-station
event is deliberately overdetermined: the extra observations stabilize the fit and
let us measure disagreement with the model.

## 3. Measurement error and residuals

A real station time does not lie exactly on an ideal plane. We write

$$
t_i^{\mathrm{obs}}
=t_0+\frac{\mathbf u\cdot\mathbf r_i}{c}+\epsilon_i,
$$

where $\epsilon_i$ includes measurement noise and mismatch between the real shower
and our plane approximation.

Define the raw timing residual as

$$
\boxed{
e_i=t_i^{\mathrm{obs}}-t_i^{\mathrm{pred}}
}.
$$

The sign has a direct interpretation:

- $e_i>0$: observed later than predicted;
- $e_i<0$: observed earlier than predicted;
- $e_i=0$: exact agreement with the model.

For example, if a station is observed $18$ ns later than predicted, then

$$
\boxed{e_i=+18\ \mathrm{ns}},
$$

not $-18$ ns. The sign follows from “observed minus predicted.”

## 4. Ordinary least squares

Simply adding residuals is unsuitable because positive and negative errors can
cancel. For example,

$$
(+100\ \mathrm{ns})+(-100\ \mathrm{ns})=0
$$

even though both predictions are poor.

Ordinary least squares instead minimizes the residual sum of squares:

$$
\boxed{
\mathrm{RSS}=\sum_{i=1}^{N}e_i^2
}.
$$

The model problem is

$$
\underset{t_0,\mathbf u}{\operatorname{minimize}}
\sum_{i=1}^{N}
\left[
t_i^{\mathrm{obs}}
-t_0
-\frac{\mathbf u\cdot\mathbf r_i}{c}
\right]^2.
$$

Squaring prevents cancellation, penalizes large errors more strongly, creates a
smooth objective, and leads to convenient linear algebra. It also makes ordinary
least squares sensitive to extreme outliers, which is why residual diagnosis
remains essential.

The mean squared error is

$$
\mathrm{MSE}=\frac{1}{N}\sum_i e_i^2,
$$

and the root-mean-squared error is

$$
\mathrm{RMSE}
=\sqrt{\frac{1}{N}\sum_i e_i^2}.
$$

For a fixed dataset, minimizing RSS and MSE gives the same parameter estimate
because $1/N$ is constant. RMSE is useful for reporting because it has the original
time unit, nanoseconds.

## 5. Why timing uncertainty changes each station's influence

Auger supplies a start-time uncertainty $dt_i$ for each station. Divide the raw
residual by that uncertainty:

$$
\boxed{
q_i=\frac{e_i}{dt_i}
}.
$$

The dimensionless $q_i$ is a standardized residual, sometimes called a pull.

- $q_i=+1$: observed one stated uncertainty later than predicted;
- $q_i=-3$: observed three stated uncertainties earlier than predicted;
- $q_i\approx0$: close agreement relative to the timing precision.

Suppose two stations both have $20$ ns residuals, but

$$
dt_1=5\ \mathrm{ns},
\qquad
dt_2=20\ \mathrm{ns}.
$$

Then

$$
q_1=4,
\qquad
q_2=1.
$$

The first standardized residual is four times as large. After squaring, its
chi-square contribution is sixteen times as large:

$$
q_1^2=16,
\qquad
q_2^2=1.
$$

This distinction matters:

- standardized-residual magnitude: four times larger;
- contribution to the squared objective: sixteen times larger.

## 6. Weighted least squares and chi-square

Weighted least squares minimizes

$$
\boxed{
\chi^2
=\sum_{i=1}^{N}
\left(\frac{e_i}{dt_i}\right)^2
=\sum_{i=1}^{N}w_i e_i^2
},
$$

where

$$
\boxed{
w_i=\frac{1}{dt_i^2}
}.
$$

The complete objective is

$$
\boxed{
\underset{t_0,\mathbf u}{\operatorname{minimize}}
\sum_{i=1}^{N}
\left[
\frac{
t_i^{\mathrm{obs}}-t_0-\mathbf u\cdot\mathbf r_i/c
}{dt_i}
\right]^2
}.
$$

At the final physical stage, this is subject to

$$
\lVert\mathbf u\rVert=1,
\qquad
u_z<0.
$$

Smaller uncertainty means greater weight. Halving an uncertainty multiplies its
weight by four.

### Why use `dt`, not `signal`, for the baseline weight?

`dt` directly estimates uncertainty in the fitted measurement `t`. Signal is a
detector-response magnitude, not itself a timing uncertainty. A strong signal may
correlate with better timing, but we should test that relationship rather than
inventing a signal-weight formula.

Later, residuals can be plotted against signal to test whether `dt` has captured
all signal-dependent timing behaviour.

### Statistical interpretation

If independent station errors satisfy

$$
\epsilon_i\sim\mathcal N(0,dt_i^2),
$$

then maximizing the probability of the observed timings is equivalent to
minimizing

$$
\sum_i\frac{e_i^2}{dt_i^2}.
$$

Thus, weighted least squares is also the maximum-likelihood estimate under the
independent Gaussian-error model. These are assumptions to diagnose, not facts
guaranteed by the file format.

## 7. Weighted-mean analogy and derivation

For measurements $t_i$ of one common value $\mu$, define

$$
S(\mu)=\sum_i w_i(t_i-\mu)^2.
$$

At the minimum,

$$
\frac{dS}{d\mu}
=-2\sum_i w_i(t_i-\mu)=0.
$$

Therefore,

$$
\sum_iw_it_i=\mu\sum_iw_i,
$$

and

$$
\boxed{
\mu=\frac{\sum_iw_it_i}{\sum_iw_i}
}.
$$

For

$$
t_1=100\pm5\ \mathrm{ns},
\qquad
t_2=110\pm20\ \mathrm{ns},
$$

the weights are $0.04$ and $0.0025$, giving

$$
\bar t_w
=\frac{(0.04)(100)+(0.0025)(110)}{0.0425}
\approx100.59\ \mathrm{ns}.
$$

The result lies closer to the more precise measurement. Matrix weighted least
squares applies this same idea to several direction parameters at once.

## 8. The design matrix

Expand the prediction:

$$
t_i^{\mathrm{pred}}
=t_0+\frac{x_i u_x+y_i u_y+z_i u_z}{c}.
$$

For one station, define the row

$$
\mathbf X_i=
\begin{bmatrix}
1 & x_i/c & y_i/c & z_i/c
\end{bmatrix}
$$

and the parameter vector

$$
\mathbf p=
\begin{bmatrix}
t_0\\u_x\\u_y\\u_z
\end{bmatrix}.
$$

Then

$$
t_i^{\mathrm{pred}}=\mathbf X_i\mathbf p.
$$

Stacking all stations produces

$$
\boxed{
\mathbf t\approx\mathbf X\mathbf p
}.
$$

For 24 selected stations,

$$
\mathbf X:24\times4,
\qquad
\mathbf p:4\times1,
\qquad
\mathbf t:24\times1.
$$

The product has shape

$$
(24\times4)(4\times1)=(24\times1),
$$

so it produces one predicted time per station.

Each row represents one station's timing equation. The columns represent the
intercept and the $x$, $y$, and $z$ timing contributions.

Because 24 observations constrain only four raw parameters, the system is
overdetermined. Noise and model mismatch mean no parameter vector will generally
satisfy all equations exactly, so we seek the least-disagreeing solution.

## 9. Matrix weighted least squares

Define

$$
\mathbf e=\mathbf t-\mathbf X\mathbf p
$$

and the diagonal weight matrix

$$
\boxed{
\mathbf W=
\operatorname{diag}
\left(
\frac{1}{dt_1^2},\ldots,\frac{1}{dt_N^2}
\right)
}.
$$

The off-diagonal entries are zero because our baseline assumes different stations'
timing errors are uncorrelated. The times themselves are related through the same
shower; it is specifically their measurement errors that are assumed independent.
Nonzero off-diagonal covariance terms would represent shared timing or calibration
errors.

The matrix objective is

$$
\boxed{
\chi^2
=(\mathbf t-\mathbf X\mathbf p)^\mathsf T
\mathbf W
(\mathbf t-\mathbf X\mathbf p)
}.
$$

Differentiation produces the weighted normal equations

$$
\boxed{
\mathbf X^\mathsf T\mathbf W\mathbf X\,\mathbf p
=\mathbf X^\mathsf T\mathbf W\mathbf t
}.
$$

A formal textbook expression is

$$
\hat{\mathbf p}
=(\mathbf X^\mathsf T\mathbf W\mathbf X)^{-1}
\mathbf X^\mathsf T\mathbf W\mathbf t.
$$

We will not explicitly calculate that inverse. Direct inversion performs
unnecessary work, introduces additional floating-point error, and behaves poorly
for singular or nearly singular geometry. A least-squares solver based on QR or SVD
is more stable and can expose rank problems.

### Whitening the equations

Define

$$
\mathbf D=
\operatorname{diag}
\left(
\frac{1}{dt_1},\ldots,\frac{1}{dt_N}
\right),
$$

so $\mathbf W=\mathbf D^\mathsf T\mathbf D$. Set

$$
\mathbf A=\mathbf D\mathbf X,
\qquad
\mathbf b=\mathbf D\mathbf t.
$$

Then weighted least squares becomes ordinary least squares on the whitened system:

$$
\boxed{
\underset{\mathbf p}{\operatorname{minimize}}
\lVert\mathbf b-\mathbf A\mathbf p\rVert^2
}.
$$

Operationally, this divides each station equation and observed time by that
station's `dt`.

## 10. Weighted coordinate centring

The raw Auger coordinates and times can be numerically large even though only their
differences determine direction. Define

$$
\bar{\mathbf r}_w
=\frac{\sum_iw_i\mathbf r_i}{\sum_iw_i},
\qquad
\bar t_w
=\frac{\sum_iw_it_i}{\sum_iw_i}.
$$

Now define centred quantities

$$
\Delta\mathbf r_i=\mathbf r_i-\bar{\mathbf r}_w,
\qquad
\Delta t_i=t_i-\bar t_w.
$$

The centred prediction is

$$
\boxed{
\Delta t_i
=\frac{\mathbf u\cdot\Delta\mathbf r_i}{c}
}.
$$

The common time offset disappears. The centred design row is

$$
\begin{bmatrix}
\Delta x_i/c & \Delta y_i/c & \Delta z_i/c
\end{bmatrix},
$$

and the unknown vector is simply

$$
\begin{bmatrix}u_x&u_y&u_z\end{bmatrix}^{\mathsf T}.
$$

After estimating $\mathbf u$, the original intercept can be recovered as

$$
\boxed{
t_0=\bar t_w-\frac{\mathbf u\cdot\bar{\mathbf r}_w}{c}
}.
$$

Centring improves numerical behaviour and gives the reference time a local physical
meaning. It is not the same as scaling columns, normalizing a vector, or dividing a
residual by its uncertainty.

## 11. Why equal station heights cannot determine $u_z$ directly

If every selected station has exactly the same height $z_0$, then after centring

$$
\Delta z_i=z_i-\bar z=0
$$

for every station. The entire $\Delta z_i/c$ design column is zero, so

$$
\Delta t_i
=\frac{u_x\Delta x_i+u_y\Delta y_i}{c}.
$$

The timings directly determine only $u_x$ and $u_y$. Before centring, the constant
term $u_z z_0/c$ is indistinguishable from the intercept $t_0$.

The unit constraint provides the magnitude

$$
u_z=\pm\sqrt{1-u_x^2-u_y^2},
$$

and downward propagation provides the negative sign. Small real altitude changes
can technically add $u_z$ information, but near-coplanar geometry can still make an
unconstrained vertical estimate unstable.

## 12. The raw linear estimate and the unit-vector constraint

The linear solver treats $u_x$, $u_y$, and $u_z$ as independent. It does not know
that

$$
u_x^2+u_y^2+u_z^2=1.
$$

With noise and a curved real front, it might return

$$
\mathbf u_{\mathrm{raw}}=(0.50,0.60,-0.70),
$$

whose magnitude is

$$
\lVert\mathbf u_{\mathrm{raw}}\rVert
=\sqrt{0.25+0.36+0.49}
\approx1.049.
$$

Normalizing it,

$$
\mathbf u_{\mathrm{norm}}
=\frac{\mathbf u_{\mathrm{raw}}}
{\lVert\mathbf u_{\mathrm{raw}}\rVert},
$$

produces a valid unit vector and a useful initial guess. It is not necessarily the
best final fit because rescaling afterward does not minimize the weighted timing
objective or properly refit the event-time offset.

The final fit must search among physical unit vectors while minimizing $\chi^2$.

If an unconstrained horizontal result satisfies

$$
u_x^2+u_y^2>1,
$$

then no real $u_z$ can complete it into a unit vector. This is an unphysical raw
estimate, not evidence of an imaginary shower. It can flag noise, poor geometry,
outliers, incorrect units, or model inadequacy.

## 13. Parameterizing a physical downward direction

For learning purposes, temporarily measure azimuth counterclockwise from $+x$ in
the horizontal plane. A downward propagation unit vector can be written as

$$
\boxed{
\mathbf u(\theta,\phi_{\mathrm{prop}})
=
\left(
\sin\theta\cos\phi_{\mathrm{prop}},
\sin\theta\sin\phi_{\mathrm{prop}},
-\cos\theta
\right)
}.
$$

For $0\leq\theta\leq90^\circ$, this parameterization automatically ensures

$$
\lVert\mathbf u\rVert=1
\qquad\text{and}\qquad
u_z\leq0.
$$

The temporary propagation angles are recovered using

$$
\boxed{
\theta=\cos^{-1}(-u_z)
},
$$

$$
\boxed{
\phi_{\mathrm{prop}}=\operatorname{atan2}(u_y,u_x)
}.
$$

Auger's exact axis orientation, azimuth zero, rotation direction, and meaning of
published arrival direction must be verified before comparing numerical angles.

### Why `atan2` is required

Ordinary

$$
\tan^{-1}(u_y/u_x)
$$

cannot distinguish opposite quadrants because tangent repeats every $180^\circ$.
It also fails when $u_x=0$. The two-argument function uses both component signs:

$$
\operatorname{atan2}(y,x)=
\begin{cases}
\tan^{-1}(y/x), & x>0,\\
\tan^{-1}(y/x)+\pi, & x<0,\ y\geq0,\\
\tan^{-1}(y/x)-\pi, & x<0,\ y<0,\\
+\pi/2, & x=0,\ y>0,\\
-\pi/2, & x=0,\ y<0.
\end{cases}
$$

The direction is undefined if $x=y=0$.

In NumPy, the argument order is `y, x`:

```python
phi_radians = np.arctan2(u_y, u_x)
phi_degrees = np.degrees(phi_radians) % 360
```

For $u_x=-0.5$ and $u_y=+0.5$, ordinary arctangent returns $-45^\circ$,
whereas `atan2` correctly identifies quadrant II and returns $135^\circ$.

### Propagation direction versus sky-arrival direction

Because $\mathbf a=-\mathbf u$, their temporary horizontal azimuths differ by
$180^\circ$:

$$
\boxed{
\phi_{\mathrm{sky}}
=(\phi_{\mathrm{prop}}+180^\circ)\bmod360^\circ
}.
$$

For example, a propagation azimuth of $50^\circ$ corresponds to a sky-arrival
azimuth of

$$
\boxed{230^\circ},
$$

not $130^\circ$.

## 14. The constrained weighted fit

Choose a reference position $\mathbf r_{\mathrm{ref}}$ near the selected stations.
The physical prediction is

$$
t_i^{\mathrm{pred}}
=t_{\mathrm{ref}}
+\frac{
\mathbf u(\theta,\phi)\cdot
(\mathbf r_i-\mathbf r_{\mathrm{ref}})
}{c}.
$$

We fit the three physical parameters

$$
t_{\mathrm{ref}},\quad\theta,\quad\phi
$$

by minimizing

$$
\boxed{
\chi^2(t_{\mathrm{ref}},\theta,\phi)
=\sum_i
\left[
\frac{
t_i^{\mathrm{obs}}
-t_{\mathrm{ref}}
-\mathbf u(\theta,\phi)\cdot
(\mathbf r_i-\mathbf r_{\mathrm{ref}})/c
}{dt_i}
\right]^2
}.
$$

Because $\mathbf u(\theta,\phi)$ is built from sines and cosines, every candidate
has unit length and the required downward sign. The model is nonlinear in the
angles, but it has only three fitted parameters.

The planned numerical sequence is:

1. Calculate a fast linear weighted-least-squares estimate.
2. Inspect its rank, conditioning, and raw magnitude.
3. Convert it into approximate physical angles.
4. Use those angles as the initial guess for the constrained fit.
5. Return the physical vectors, predicted times, residuals, and fit diagnostics.

## 15. Angular separation

After freezing our prediction, compare our unit sky vector with the Auger reference
unit vector. For unit vectors,

$$
\mathbf a_{\mathrm{ours}}\cdot\mathbf a_{\mathrm{Auger}}
=\cos\Delta\psi.
$$

Therefore,

$$
\boxed{
\Delta\psi
=\cos^{-1}
\left(
\mathbf a_{\mathrm{ours}}\cdot\mathbf a_{\mathrm{Auger}}
\right)
}.
$$

Numerical code must clip the dot product into $[-1,1]$ before applying inverse
cosine because floating-point rounding can produce values just outside that range.

Angular separation avoids the wrap-around problem in which $359^\circ$ and
$1^\circ$ look numerically far apart even though they are physically close.

## 16. Implementation contract

The reusable plane-front fitter will eventually accept selected arrays of:

- `x`, `y`, `z` in metres;
- `t` and `dt` in nanoseconds.

It should return at least:

- the raw linear estimate;
- the constrained propagation vector $\mathbf u$;
- the sky vector $\mathbf a=-\mathbf u$;
- temporary mathematical angles and later verified Auger-convention angles;
- predicted station times;
- raw and standardized residuals;
- $\chi^2$, degrees of freedom, and reduced $\chi^2$;
- matrix-rank and conditioning information;
- clear failure reasons for invalid geometry or optimization.

The function must not read official zenith, azimuth, core, or other reconstructed
answers while estimating direction.

## 17. Common mistakes to guard against

- Reversing the residual sign: it is observed minus predicted.
- Using $c$ in metres per second while times remain in nanoseconds.
- Confusing propagation direction with sky-arrival direction.
- Assuming normalization of the raw solution is the final constrained optimum.
- Using `arctan(y/x)` instead of `atan2(y, x)`.
- Swapping the `atan2` arguments.
- Comparing azimuths before verifying Auger's convention.
- Explicitly inverting a nearly singular matrix.
- Treating station times as independent rather than their measurement errors.
- Using official reconstructed fields as baseline inputs.

## 18. Understanding checks and settled answers

1. If $u_x>0$ while $y$ and $z$ are fixed, a larger-$x$ station is predicted
   later because $u_xx_i/c$ increases.
2. Moving the coordinate origin changes $t_0$ because the front reaches the new
   reference point at a different time; it does not change $\mathbf u$.
3. A positive residual means the station was observed later than predicted.
4. Equal $20$ ns residuals with $5$ ns and $20$ ns uncertainties have pulls $4$
   and $1$; their chi-square contributions are in a $16:1$ ratio.
5. One row of $\mathbf X$ is one station's timing equation.
6. With 24 stations, $\mathbf X$ is $24\times4$, $\mathbf p$ is $4\times1$, and
   $\mathbf t$ is $24\times1$.
7. Equal station heights remove direct sensitivity to $u_z$; the unit-vector
   condition provides its magnitude and downward physics provides its sign.
8. A normalized raw vector is a useful initial guess but does not necessarily
   minimize the constrained weighted objective.
9. A propagation azimuth of $50^\circ$ corresponds to a temporary sky azimuth of
   $230^\circ$.
10. If $u_x^2+u_y^2>1$, the raw unconstrained horizontal estimate is unphysical.

## 19. Key takeaways

- Direction is encoded in relative station timing, not the absolute event time.
- `dt` determines principled inverse-variance weights.
- The design matrix expresses every station timing equation in one system.
- Centring removes irrelevant offsets and improves numerical stability.
- QR- or SVD-based solvers are safer than an explicit matrix inverse.
- The linear result is a diagnostic and initialization; the constrained fit is the
  physical baseline.
- Vector signs and angle conventions must be tested rather than assumed.
- Auger's official direction is withheld during fitting and used only afterward
  for evaluation.

