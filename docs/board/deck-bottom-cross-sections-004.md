# Board deck and bottom cross-sections — DOM-004

Status: normative geometry contract for the next board-surface implementation. This document extends the existing station-based prototype; it does not claim that the features below are implemented.

## 1. Scope

Define a deterministic cross-section model for the board deck and bottom, including transverse curvature, bottom channels, deck standing areas, local transitions and asymmetric shaping. The model must loft through longitudinal stations and remain compatible with the existing millimetre coordinate convention (X nose-to-tail, Y port/starboard, Z up).

This contract does not redefine the global coordinate system, planform or rocker. Station X and the board's planform width remain owned by the longitudinal/outline model. The cross-section model supplies the transverse profile at a given X.

## 2. Coordinate and reference rules

- Each section is evaluated at a longitudinal coordinate X.
- The section's local lateral coordinate is normalized as u = 2Y/W(X), where W(X) is the full local width and u is in [-1,+1].
- u=0 is the centerline; u=-1 and u=+1 are the port and starboard rail boundaries.
- Bottom and deck are separate functions: Zb(X,u) and Zd(X,u). Thickness is T(X,u)=Zd-Zb.
- The section model must not assume that deck and bottom share the same transverse curvature.
- If W(X) is zero or below the geometry tolerance, the section is a tip condition and is not evaluated as an ordinary full-width section.
- Symmetry is an explicit mode, not an assumption. In symmetric mode, mirrored samples at ±u must agree within tolerance.

The existing prototype stores dimensions in millimetres. Persisted project values remain millimetres for compatibility with its JSON format; internal numerical kernels may use SI only if conversion occurs at a single documented boundary.

## 3. Data model

A section definition contains:

- stable `section_id`;
- `x_mm` or a station reference;
- `symmetry`: `symmetric` or `asymmetric`;
- independent bottom and deck profile definitions;
- ordered transverse control points;
- optional named feature regions;
- interpolation and continuity settings;
- a schema version.

Each transverse control point contains:

- stable `point_id`;
- normalized lateral position `u`;
- vertical offset in millimetres relative to the applicable reference surface;
- optional incoming/outgoing handles;
- continuity mode: `corner`, `smooth`, or `symmetric`.

Control points must be strictly ordered by u. Endpoints at u=-1 and u=+1 are rail-boundary constraints. A centerline point at u=0 is required for symmetric sections; asymmetric sections may still use a centerline anchor but are not forced to mirror.

Feature regions are parameterized intervals in u and may describe a standing area, concave, channel, V transition, chine or rail tuck. Regions modify or constrain the profile; they do not create independent overlapping surfaces.

## 4. Supported profile primitives

The first implementation must support the following analytic profile families, independently for deck and bottom:

1. Flat: constant transverse Z offset.
2. V-bottom: piecewise linear or smooth two-sided rise from a defined keel/centerline reference toward the rails. The V depth and transition width are explicit parameters.
3. Single concave: one smooth central depression with explicit depth and half-width.
4. Double concave: two depressions separated by a central spine; left/right depths and positions may differ in asymmetric mode.
5. Compound profile: ordered combination of the above with explicit blend intervals.

A profile family is only a parameterization shortcut. The canonical evaluated result is a single continuous function Z(X,u), not a stack of independent surfaces.

## 5. Deck-specific features

The deck supports:

- convex dome/crown;
- near-flat standing area with independently controlled width;
- local recessed standing zone;
- optional rail-side shoulders or bevel/chine transitions.

A standing area is a bounded feature region with start/end lateral positions and a target slope/curvature constraint. It must blend into the surrounding deck without a positional jump. The model must not silently flatten the entire deck when only a local standing zone is requested.

## 6. Bottom-specific features

The bottom supports:

- flat, V, single concave and double concave;
- longitudinally varying concave depth and width;
- local channel regions;
- optional spine/keel feature;
- independent port and starboard parameters in asymmetric mode.

Bottom concave depth is measured relative to the declared local baseline, not relative to a moving rail point. This prevents ambiguous sign conventions when width or rocker changes.

## 7. Blending and continuity

Each feature has a finite blend interval. A blend definition includes start/end u, blend type and target continuity.

- G0: positions meet.
- G1: tangent direction is continuous.
- G2: curvature is continuous.

Default transitions for the first implementation are G1. G2 is required only where explicitly selected and supported by the chosen spline basis. A requested continuity that cannot be satisfied must return a validation error; it must not silently downgrade.

Blend intervals must be ordered, non-overlapping unless an explicit composition rule is defined, and contained in [-1,+1]. Adjacent feature definitions that share a boundary must agree on the boundary value within the position tolerance.

## 8. Evaluation and loft algorithm

For a requested X:

1. Evaluate the planform width W(X) and the existing longitudinal reference surfaces.
2. Resolve the bracketing section stations.
3. Interpolate section parameters longitudinally using the project's declared interpolation policy; do not interpolate raw control-point arrays unless their topology and u coordinates match.
4. Evaluate bottom and deck transverse profiles at common u samples.
5. Add the longitudinal reference heights exactly once.
6. Check local thickness and surface validity.
7. Emit paired bottom/deck section curves for the loft kernel.

If neighboring sections have different feature counts or control-point topology, first map them to a common canonical representation (for example, a fixed-u evaluation grid plus feature metadata). Do not pair control points merely by array index.

Sampling density is controlled by geometric error and curvature, not only by a fixed perimeter sample count. A fixed sampling mode may remain available for deterministic regression tests.

## 9. Invariants and validation

A valid ordinary section must satisfy:

- all numeric inputs and evaluated coordinates are finite;
- control-point u values are strictly increasing;
- all u values lie within [-1,+1];
- deck is strictly above bottom: T(X,u) > minimum_thickness_mm for every validated sample;
- no self-intersection in either transverse profile;
- no fold-over or inversion in the loft between adjacent sections;
- feature and blend intervals are valid and ordered;
- symmetry constraints hold when symmetry is enabled;
- the rail endpoints connect to the declared rail boundary and are not left as gaps.

Validation must sample adaptively near high curvature, feature boundaries and blend endpoints. A coarse preview grid is not sufficient for final validation.

## 10. Failure cases

Reject the section with a structured error when any of the following occurs:

- duplicate or unordered u control points;
- feature interval outside [-1,+1];
- overlapping features without a defined composition order;
- negative or zero local thickness;
- deck/bottom crossing between samples or within a spline span;
- impossible G1/G2 constraint;
- discontinuous feature boundary;
- non-finite interpolation result;
- mismatched topology that cannot be mapped to a common loft representation;
- section evaluated at a zero-width tip as if it were a regular section.

Errors should include `section_id`, X, feature/control-point ID where available, and the violated invariant.

## 11. Serialization contract

Use explicit units in field names for persisted scalar dimensions. Example shape (illustrative, not yet the full project schema):

```json
{
  "schema": "surfwing.board.section.v1",
  "section_id": "section-mid",
  "x_mm": 0,
  "symmetry": "symmetric",
  "bottom": {
    "type": "single_concave",
    "depth_mm": 2.0,
    "half_width_u": 0.55,
    "blend": {"start_u": 0.55, "end_u": 0.9, "continuity": "G1"}
  },
  "deck": {
    "type": "dome_with_standing_area",
    "crown_mm": 5.0,
    "standing_area": {"start_u": -0.35, "end_u": 0.35, "recess_mm": 0.0}
  }
}
```

Unknown schema versions must be rejected. Defaults must be explicit and versioned; loaders must not reinterpret missing fields differently between releases.

## 12. Acceptance tests

The section kernel is accepted only when all tests below pass:

1. Flat section: Z is constant across u; maximum deviation <= 0.01 mm.
2. Symmetric V: mirrored Z samples differ by <= 0.01 mm at 101 paired u samples.
3. Single concave: center depression equals configured depth within 0.01 mm; profile returns to baseline at the declared boundary.
4. Double concave: two local minima and one intervening spine are detected at expected positions within 0.005 in normalized u.
5. Deck standing area: requested central width is maintained within 0.5 mm lateral position and has no G0 discontinuity.
6. Asymmetric section: port/starboard parameters remain distinct and survive save/load without mirroring.
7. Thickness: deliberately crossing deck/bottom profiles are rejected, including a crossing placed between coarse sample points.
8. Continuity: G1 tangent mismatch <= 0.1 degree; G2 curvature mismatch <= 1% where G2 is requested.
9. Loft: adjacent sections with differing control-point counts produce a valid common representation or a clear rejection; no index-based silent pairing.
10. Serialization: round-trip preserves all IDs, units, feature types and parameter values within 1e-9 relative numeric tolerance.
11. Regression: existing starter JSON still loads and generates the current prototype mesh unchanged until the new section schema is explicitly selected.

## 13. Integration with the current repository

- Existing `BoardStation` fields `deck_crown_mm` and `bottom_concave_mm` are legacy scalar approximations. Preserve their loader and behavior for existing starter files.
- Introduce the richer section model as a versioned additive schema; do not silently reinterpret legacy fields.
- Keep planform width and longitudinal bottom reference owned by the board geometry model.
- Mesh generation must consume evaluated deck/bottom section curves and retain the existing watertightness, positive-volume and export checks.
- This is a design contract. Implementation, GUI editing, STEP/B-rep support and manufacturing qualification remain separate work items.
