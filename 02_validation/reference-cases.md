# Beam analysis reference cases

These deterministic hand-calculation cases are for checking reactions, shear,
moment, and elastic deflection after the beam analysis is implemented. They do
not validate the AISC strength-capacity check or establish that a real beam is
safe.

## Shared assumptions

- Linear-elastic Euler-Bernoulli beam behavior, constant `EI`, and small
  deflections.
- Use `E = 29,000 ksi` and W12x26 strong-axis `Ix = 204 in^4` for deflection
  cases. These are rounded reference inputs; use the exact values from the
  chosen database consistently when testing the app.
- For the bending-stress reference only, use `Sx = 33.4 in^3`.
- Use `1 ft = 12 in`, `1 kip/ft = 1/12 kip/in`, and `1 kip-ft = 12 kip-in`.
- Compare unrounded calculation results, not just plotted pixels. A tolerance
  of 0.1% is suitable for the listed results when using the stated rounded
  section properties; use an absolute tolerance near zero.

## Case 1: Simply supported beam with full-span uniform load

**Inputs:** `L = 20 ft`; W12x26; `w = 1 kip/ft` from `x = 0` to `20 ft`.

| Quantity | Expected result |
|---|---:|
| Left and right reactions | `10 kip` each |
| Shear, for `x` in ft | `V(x) = 10 - x kip` |
| Moment, for `x` in ft | `M(x) = 10x - x^2/2 kip-ft` |
| Maximum moment | `50 kip-ft` at `x = 10 ft` |
| Maximum deflection | `0.608519 in` downward at midspan |
| `L/360` limit | `0.666667 in`; deflection check passes |
| Elastic bending stress `M/Sx` | `17.964 ksi` |

Use the closed-form deflection `5wL^4/(384EI)` with all values converted to
consistent inch-based units.

For the app's limited compact-section flexural check, W12x26 has
`bf/(2tf) = 8.54` and the conservative web estimate `(d - 2tf)/tw = 49.74`,
both below the A992 compact limits. With continuous bracing,
`Mn = Fy Zx = 1,860 kip-in` and the ASD allowable moment is
`Mn/(1.67 * 12) = 92.814 kip-ft`. The `50 kip-ft` demand therefore has a
utilization of `53.9%` and passes this limited check. This does not validate any
excluded limit state or load combination.

## Case 2: Simply supported beam with centered point load

**Inputs:** `L = 12 ft`; W12x26; `P = 6 kip` downward at `x = 6 ft`.

| Quantity | Expected result |
|---|---:|
| Left and right reactions | `3 kip` each |
| Shear | `+3 kip` before the load, a `6 kip` jump at the load, then `-3 kip` |
| Maximum moment | `18 kip-ft` at midspan |
| Maximum deflection | `0.063091 in` downward at midspan |

Use the closed-form deflection `PL^3/(48EI)`.

## Case 3: Cantilever with end point load

**Inputs:** fixed support at `x = 0`; `L = 6 ft`; W12x26; `P = 1 kip`
downward at the free end.

| Quantity | Expected result |
|---|---:|
| Fixed vertical reaction | `1 kip` upward |
| Fixed reaction moment | `6 kip-ft`, counterclockwise |
| Internal moment | Hogging moment of `6 kip-ft` at the fixed end, reducing linearly to zero at the free end |
| Maximum deflection | `0.021030 in` downward at the free end |

Use the closed-form tip deflection `PL^3/(3EI)`. The free end must have zero
moment, and the fixed end must have zero deflection and slope.

## Case 4: Simply supported beam with a symmetric partial uniform load

**Inputs:** `L = 12 ft`; W12x26; `w = 0.5 kip/ft` from `x = 3 ft` to `9 ft`.

| Quantity | Expected result |
|---|---:|
| Total applied load | `3 kip` at `x = 6 ft` |
| Left and right reactions | `1.5 kip` each |
| Shear | `+1.5 kip` from `0` to `3 ft`; linear to zero at `6 ft`; linear to `-1.5 kip` at `9 ft`; constant to `12 ft` |
| Maximum moment | `6.75 kip-ft` at `x = 6 ft` |
| Maximum deflection | `0.028095 in` downward at midspan |

For the left half, the moment is `M(x) = 1.5x` for `0 <= x <= 3 ft`, and
`M(x) = 1.5x - 0.25(x - 3)^2` for `3 <= x <= 6 ft`, with `M` in kip-ft and
`x` in ft. Use symmetry for the right half. The midpoint deflection can be
checked by virtual work:

`delta_mid = 12^3/EI * integral_0^6[M(x) * x dx] = 0.028095 in`

with the integral evaluated using consistent units.

## Section-property source

Use the free, standard AISC Shapes Database v16.0 from the
[official AISC download page](https://www.aisc.org/aisc/publications/steel-construction-manual/shapes-database-v160/).
The page identifies the standard database as shapes current with the 16th
Edition *Steel Construction Manual*. Confirm the W12x26 row and units in the
downloaded workbook before treating these rounded values as the app's catalog
record. Do not use an independently copied web table as the source of truth.

These cases do not test design strength. Validate any AISC ASD capacity or
pass/fail implementation separately against the applicable AISC Specification
and a hand calculation with the exact assumptions and section data recorded.
