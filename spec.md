# Beam Designer

## Purpose

Provide an educational, preliminary analysis of a single-span beam: reactions,
shear, moment, and deflection diagrams, plus limited checks for flexural strength
and service deflection.

This tool is not a substitute for a complete structural design or review by a
qualified professional. A passing result applies only to the checks and
assumptions listed here; it does not establish that a beam is safe for
construction.

## Initial scope

- One straight, prismatic beam with a single span.
- Supports: simply supported or cantilever.
- Loads: point loads and constant distributed loads, including loads over only
  part of the span.
- Elastic, linear analysis with small deflections and strong-axis bending.
- Steel W-shapes only. Lumber is deferred until species, grade, actual
  dimensions, and applicable design-value adjustments can be represented.
- One user-specified service-level load case. The user is responsible for
  including the applicable loads; the app does not generate load combinations.

## Inputs

- Support condition and span.
- One or more downward or upward point loads, each with a position.
- One or more downward or upward uniform loads, each with start and end
  positions.
- A W-shape selected by designation from a sourced section-property catalog.
- A992 steel for the initial strength check.
- Deflection limit, defaulting to `L/360`. Show that this is a configurable
  criterion, not a universal requirement.

Use a consistent displayed unit system (ft, kip, and kip/ft for loads; in for
section properties and deflection). Convert inputs to consistent internal units
before calculations.

## Section properties and material data

The W-shape catalog must be based on a named, versioned AISC Shapes Database.
Keep the source/version and units with the catalog data in `01_data/`. At a
minimum, each shape needs its designation, strong-axis moment of inertia `Ix`,
and elastic section modulus `Sx`. Store material properties separately from
shape geometry, including the steel grade and yield strength used by the
strength check.

Do not silently substitute missing, rounded, or guessed properties. Show the
selected shape, grade, and source information where users can inspect them.
Lumber data is out of the initial release; adding it requires species- and
grade-specific design values and actual dimensions, not just a nominal size.

## Calculations and checks

- Calculate support reactions and shear and moment diagrams using statics.
- Calculate the elastic deflection curve for the stated supports and loads.
- Report maximum absolute moment and deflection, with their locations.
- For the flexural strength check, treat the entered load case as an ASD
  service-level load case and use the ASD provisions of AISC 360-22 for the
  selected shape and A992 steel.
- The initial strength check assumes the beam is continuously laterally braced
  over its span. Only a W-shape passing the app's compact-section screen is
  checked; use `Mn = Fy Zx` and `Ma = Mn / 1.67` for that limited case. Report
  other shapes as not checked rather than applying a generic allowable stress.
  Do not imply that lateral-torsional buckling has been checked.
- Compare maximum service deflection with the selected limit (default `L/360`).
- Show the demand, capacity or limit, utilization where applicable, and a
  pass/fail result for each check. Do not show a pass when required inputs or
  section data are missing.

The initial release does not check shear strength, lateral-torsional buckling,
noncompact/slender-section local-buckling capacity, bearing, connections,
vibration, fire, or load combinations. For the compactness screen, use the
conservative web slenderness estimate `(d - 2tf)/tw` because the catalog does
not include clear web depth. Show this limitation alongside the results.

## Outputs

- Beam diagram with supports and labeled loads.
- Shear, moment, and deflection diagrams with units and sign conventions.
- Reactions and maximum moment and deflection values and locations.
- Separate flexural-strength and deflection results, including the assumptions
  and limitations used for each.

## Look and feel

Use a clean, professional layout. Open with a clearly labeled example beam.
Keep the selected section, material grade, units, and design assumptions visible
so the results are understandable and reproducible.

## Validation

Use the inputs, assumptions, and expected results in
[`02_validation/reference-cases.md`](./02_validation/reference-cases.md).
Check force and moment equilibrium, reactions, diagram values, boundary
conditions, and deflections. Validate the AISC strength check separately; the
analysis reference cases do not establish strength-code compliance.

## Out of scope

- Continuous or multi-span beams.
- Lumber and engineered wood.
- Lateral-torsional buckling and all other checks listed above as excluded.
- Load-combination generation or automated code-compliance certification.
