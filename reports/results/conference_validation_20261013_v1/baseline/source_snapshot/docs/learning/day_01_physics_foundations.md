# Day 1 — Air showers, moving fronts, and direction geometry

## Purpose

This module establishes the physical and mathematical foundation for reconstructing
a cosmic-ray air shower's arrival direction from Pierre Auger surface-detector data.
It records the reasoning that must be understood before implementing the first
plane-front fit.

By the end of this module, we should be able to explain:

- what an extensive air shower and a shower front are;
- what an Auger surface station measures;
- why station positions and signal-start times contain directional information;
- how the moving-plane timing equation follows from the point-normal equation;
- the difference between propagation direction and astronomical arrival direction;
- how zenith, azimuth, unit vectors, and angular separation are related;
- which parts of the model are physical approximations.

## 1. From one cosmic ray to an extensive air shower

A cosmic ray is usually a high-energy charged particle, such as a proton or an
atomic nucleus. When it collides with a nucleus in Earth's atmosphere, it creates
secondary particles. Those particles produce further interactions, creating an
**extensive air shower**.

The shower can cover several square kilometres when it reaches the ground. The
Pierre Auger surface detector samples this shower using separated water-Cherenkov
stations. It does not place one solid detector beneath the entire shower.

### The shower front is not a material sheet

The **shower front** is a surface joining particles at approximately the same stage
of their downward propagation. It is similar to a wavefront: it helps us describe
where the leading part of the shower is at a particular time.

It is not:

- a rigid plate;
- one particle travelling from one detector to the next;
- a quantum-mechanical wavefunction;
- a physical object that must survive after hitting a station.

Different shower particles hit different stations. A particle that enters a western
station may pass through, lose energy, or be absorbed locally. It does not then move
sideways across the array to hit the eastern station. Meanwhile, particles in the
eastern part of the shower are still above the ground and arrive there later.

Each tank samples only a tiny portion of the full shower. Detecting particles in one
tank therefore does not terminate the rest of the shower. In addition, “annihilation”
specifically refers to processes such as matter–antimatter annihilation; ordinary
detector interactions are more generally energy loss, scattering, absorption, and
Cherenkov-light production.

A real front also has finite thickness and curvature. The plane in our first model
is a mathematical approximation to the leading timing surface.

## 2. What a surface-detector station provides

The most important released station-level quantities are:

| Quantity | Meaning | Released unit or role |
|---|---|---|
| `x`, `y`, `z` | Station position | metres |
| `t` | Estimated start time of the shower signal | nanoseconds |
| `dt` | Uncertainty in the start time | nanoseconds |
| `signal` | Integrated detector response | VEM |
| `dsignal` | Signal uncertainty | VEM |
| `isSelected` | Whether Auger used the station in its reconstruction | 0 or 1 |
| `pmt1`, `pmt2`, `pmt3` | Photomultiplier time traces | VEM per 25 ns bin |

VEM means **Vertical Equivalent Muon**, a calibration unit based on the response to
a muon passing vertically through a station.

The public JSON is **pseudo-raw**, not untouched electronics output. In particular,
`t` is an estimated signal-start time obtained after calibration and processing of
the photomultiplier traces.

## 3. Vectors and projection along the shower direction

Let

$$
\mathbf r=(x,y,z)
$$

be a position vector, and let $\mathbf u$ be a unit vector in the direction in
which the shower propagates.

Because $\lVert\mathbf u\rVert=1$,

$$
\mathbf u\cdot\mathbf r
$$

is the signed scalar projection of $\mathbf r$ along $\mathbf u$. The complete
vector projection is

$$
(\mathbf u\cdot\mathbf r)\mathbf u.
$$

This is why a dot product can describe how far a station lies along the shower's
propagation direction.

## 4. The stationary plane equation

The point-normal equation of a plane is

$$
\mathbf n\cdot(\mathbf x-\mathbf p)=0,
$$

where:

- $\mathbf n$ is normal to the plane;
- $\mathbf p$ is a known point on the plane;
- $\mathbf x$ is a variable candidate point.

The equation selects exactly those values of $\mathbf x$ that lie on the plane.
Expanding it gives

$$
\mathbf n\cdot\mathbf x-\mathbf n\cdot\mathbf p=0,
$$

and therefore

$$
\mathbf n\cdot\mathbf x=\mathbf n\cdot\mathbf p.
$$

Define the constant

$$
K=\mathbf n\cdot\mathbf p.
$$

The same plane can then be written as

$$
\boxed{\mathbf n\cdot\mathbf x=K}.
$$

The normal vector controls the plane's orientation. For a fixed normal, changing
$K$ moves the plane parallel to itself. If $\mathbf n$ is a unit vector, $K$
is the signed perpendicular distance from the origin. Otherwise the distance is

$$
\frac{K}{\lVert\mathbf n\rVert}.
$$

### Numerical example

Let

$$
\mathbf n=(1,2,2),\qquad \mathbf p=(1,0,2).
$$

Then

$$
K=\mathbf n\cdot\mathbf p=1(1)+2(0)+2(2)=5,
$$

so the plane is

$$
x+2y+2z=5.
$$

The point $(3,1,0)$ lies on it because

$$
3+2(1)+2(0)=5.
$$

Changing the equation to $x+2y+2z=8$ produces a parallel plane. Since
$\lVert\mathbf n\rVert=3$, the separation between the two planes is

$$
\frac{|8-5|}{3}=1.
$$

## 5. Deriving the moving-front equation

Use the following notation:

- $\mathbf p_0$: a known point on the front at $t=0$;
- $\mathbf p(t)$: that point after the front moves;
- $\mathbf x$: any candidate point in space;
- $\mathbf r_i$: the fixed position of detector station $i$;
- $\mathbf u$: the unit propagation direction of the front;
- $c$: the speed of the front, approximated as the speed of light.

In the plane-front approximation, $\mathbf u$ remains constant, so

$$
\Delta\mathbf u=0.
$$

The front changes position rather than direction. In time $t$, the known point
on the front is displaced by

$$
\Delta\mathbf p=ct\mathbf u,
$$

and therefore

$$
\boxed{\mathbf p(t)=\mathbf p_0+ct\mathbf u}.
$$

At time $t$, the point-normal equation is

$$
\mathbf u\cdot\bigl(\mathbf x-\mathbf p(t)\bigr)=0.
$$

Substitute $\mathbf p(t)$:

$$
\mathbf u\cdot\left[\mathbf x-(\mathbf p_0+ct\mathbf u)\right]=0.
$$

Expand the dot product:

$$
\mathbf u\cdot\mathbf x
-\mathbf u\cdot\mathbf p_0
-ct(\mathbf u\cdot\mathbf u)=0.
$$

Because $\mathbf u$ is a unit vector,

$$
\mathbf u\cdot\mathbf u=1.
$$

Thus,

$$
\mathbf u\cdot\mathbf x-ct=\mathbf u\cdot\mathbf p_0.
$$

Define

$$
K=\mathbf u\cdot\mathbf p_0.
$$

The moving plane is therefore

$$
\boxed{\mathbf u\cdot\mathbf x-ct=K}.
$$

An equivalent shortcut is

$$
\boxed{\mathbf u\cdot(\mathbf x-ct\mathbf u)=K}.
$$

The parentheses are essential. The expression means that if we algebraically undo
the front's displacement, the resulting point lies on the original plane. It does
not mean that the detector physically moves backward.

## 6. Arrival time at a fixed station

Station $i$ is fixed at $\mathbf r_i$. The front reaches it at time $t_i$, so
set $\mathbf x=\mathbf r_i$ and $t=t_i$:

$$
\mathbf u\cdot\mathbf r_i-ct_i=K.
$$

Solving for time gives

$$
\boxed{t_i=\frac{\mathbf u\cdot\mathbf r_i-K}{c}}.
$$

If we define

$$
t_0=-\frac{K}{c},
$$

then

$$
\boxed{t_i=t_0+\frac{\mathbf u\cdot\mathbf r_i}{c}}.
$$

The exact sign used in the final code depends on whether a vector is defined as
the downward propagation direction or the upward sky-arrival direction. We will
state that convention explicitly and test it against documented events.

### Why relative times remove the unknown offset

For two stations,

$$
t_i=t_0+\frac{\mathbf u\cdot\mathbf r_i}{c},
$$

$$
t_j=t_0+\frac{\mathbf u\cdot\mathbf r_j}{c}.
$$

Subtracting gives

$$
t_i-t_j
=
\frac{\mathbf u\cdot(\mathbf r_i-\mathbf r_j)}{c},
$$

or

$$
\boxed{c\,\Delta t_{ij}=\mathbf u\cdot\Delta\mathbf r_{ij}}.
$$

The common $t_0$ cancels. The deltas are created by subtraction; they were not
assumed in the original equations.

For visualization, we may use

$$
\Delta t_i=t_i-\min_j(t_j),
$$

so the first station has displayed time zero. During fitting, we will normally
include an intercept or centre the measurements rather than treating the earliest
station as physically special.

With Auger's metres and nanoseconds, use

$$
c=0.299792458\ \mathrm{m/ns}.
$$

Then both sides of $c\Delta t=\mathbf u\cdot\Delta\mathbf r$ have units of metres.

## 7. Why west-first can mean eastward motion

A slanted front is not an arrow. Its slope describes its **orientation**; its normal
vector describes its **motion**.

If the western part of a front is lower and the eastern part is higher:

1. the western station is reached first;
2. the entire front advances perpendicular to itself, downward and eastward;
3. the front's intersection with the ground moves from west to east;
4. the eastern station is reached later.

Therefore:

- propagation direction $\mathbf u$: downward and eastward;
- direction back toward the cosmic source $\mathbf a=-\mathbf u$: upward and westward.

[Open the interactive shower-front animation](assets/shower-front-direction.html)

The animation is a self-contained, sandboxed HTML learning asset. Open it in a
browser from VS Code and move the time slider. The fixed stations do not move; the
mathematical front advances through them.

## 8. Arrival direction, zenith, and azimuth

Let $\mathbf a$ be the unit vector pointing upward toward the direction in the sky
from which the cosmic ray arrived. If $\mathbf u$ points along the shower's downward
motion, then

$$
\boxed{\mathbf a=-\mathbf u}.
$$

Let the positive $z$-axis point upward. The **zenith angle** $\theta$ is measured
from $+z$:

$$
\boxed{\theta=\cos^{-1}(a_z)}.
$$

Thus:

- $\theta=0^\circ$: directly overhead;
- $\theta=90^\circ$: horizontal.

In the ordinary mathematical convention, where azimuth $\phi$ is measured in the
horizontal plane from $+x$ toward $+y$,

$$
\boxed{
\mathbf a=
\left(
\sin\theta\cos\phi,
\sin\theta\sin\phi,
\cos\theta
\right)
}.
$$

The inverse relations are

$$
\boxed{\theta=\cos^{-1}(a_z)},
$$

$$
\boxed{\phi=\operatorname{atan2}(a_y,a_x)}.
$$

If `atan2` returns a negative angle, add $2\pi$ to place it in $[0,2\pi)$.

Different experiments can define azimuth zero and increasing direction differently.
Before comparing code with Auger, we must verify the released coordinate and azimuth
convention. That conversion will be isolated and tested rather than assumed.

Representing direction as a unit vector avoids the angular wrap-around problem:
$359^\circ$ and $1^\circ$ are close physically even though their numerical
difference appears large.

## 9. Angular separation between two directions

For arbitrary vectors $\mathbf a$ and $\mathbf b$, the dot product satisfies

$$
\mathbf a\cdot\mathbf b
=
\lVert\mathbf a\rVert\lVert\mathbf b\rVert\cos\Delta\psi,
$$

where $\Delta\psi$ is the angle between them. If both are unit vectors,

$$
\mathbf a\cdot\mathbf b=\cos\Delta\psi.
$$

Therefore, our reconstruction error relative to Auger's released direction is

$$
\boxed{
\Delta\psi=cos^{-1}
\left(
\mathbf a_{\mathrm{ours}}\cdot
\mathbf a_{\mathrm{Auger}}
\right)
}.
$$

In numerical code, the dot product should be clipped to $[-1,1]$ before applying
`arccos`, because floating-point rounding can produce values such as
$1.0000000001$.

An angular separation of $2^\circ$ means our reconstructed direction lies two
degrees away from the released Auger direction on the unit sphere.

## 10. What is exact and what is approximate?

Within Euclidean geometry, the plane equations and vector identities above are exact.
The physical approximations are:

1. treating the shower front locally as a plane;
2. treating its propagation speed as $c$;
3. treating its direction as constant across the detector footprint;
4. representing a front with finite thickness by one estimated start time per station;
5. initially using Auger's `isSelected` station-association decision.

The real shower front is curved, and detector timings have uncertainty and outliers.
Our first plane fit is therefore a transparent baseline, not the final description of
the shower.

## 11. Connection to the research design

The planned progression is:

1. visualize station positions, relative times, and signals;
2. implement an unweighted plane-front reconstruction;
3. add timing-uncertainty weighting;
4. test robust fitting against timing outliers;
5. examine residual structure and shower-front curvature;
6. only then test whether an ML residual correction improves held-out angular error.

Official reconstructed quantities such as `sdrec.theta`, `sdrec.phi`, core position,
curvature radius, fit quality, and energy must not be used as baseline inputs. The
official direction is an evaluation reference, not an independent absolute truth.

## 12. Key takeaways

- A station detects only a local sample; it does not consume the whole shower.
- The shower front is a timing surface, not a material sheet or a wavefunction.
- A plane's normal controls orientation; $K$ controls its offset.
- The shower front moves along its normal, not along its slanted edge.
- Relative station times remove the common event-time offset.
- Timing reconstructs the propagation vector $\mathbf u$; astronomy usually reports
  the opposite, sky-pointing arrival vector $\mathbf a=-\mathbf u$.
- Unit-vector angular separation avoids azimuth wrap-around and gives the physically
  meaningful reconstruction error.

## Authoritative references

- [Pierre Auger Open Data portal](https://opendata.auger.org/)
- [Dataset description and field semantics](https://opendata.auger.org/data.php)
- [Interactive official event browser](https://opendata.auger.org/display.php)
- [Open Data concept DOI](https://doi.org/10.5281/zenodo.4487612)

