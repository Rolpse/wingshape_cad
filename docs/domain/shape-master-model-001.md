# SurfWing Shape Master Model 001

**Status:** domain-schema proposal (v0.1; not implemented)  
**Date:** 2026-11-26  
**Repository:** `Rolpse/wingshape_cad`  
**Scope:** kernel-neutral source-of-truth model for surfboards, wingfoil boards and hydrofoils.

This specification is deliberately independent of Python/C++ and of OCCT topology. It advances the domain schema while Issue #3's implementation-boundary decision remains open. It is compatible with the current analytic section prototype and the separate section-loft mesh path, but neither is yet a complete consumer of this schema.

## 1. Goals and non-goals

**Goals**
- One stable, versioned design document for board and foil products.
- Persistent semantic IDs; list position and kernel topology are never identity.
- Editable curves with anchors and incoming/outgoing handles; explicit corner/smooth intent.
- Board planform, rocker/stringer, rails, deck/bottom sections, nose/tail and mount features.
- Foil components, section stations, local frames, sweep/dihedral/twist and attachment transforms.
- Derived patch/surface recipe, feature graph, variants and measured properties.
- Deterministic validation, migration and round-trip acceptance tests.

**Not in v0.1:** production B-Rep/NURBS generation, constraint solving, interactive UI, CAM approval, or a final kernel/language choice.

## 2. Coordinate system and units

Canonical length unit: **millimetre (mm)**. Canonical angle: **radian**. Imported documents may declare metres, inches or degrees, but conversion occurs once at import; the saved canonical document is mm/rad.

Common right-handed product coordinates:
- **X:** longitudinal, nose/leading edge to tail/trailing edge (positive aft).
- **Y:** transverse, centreline to starboard (positive starboard).
- **Z:** vertical, bottom/underside toward deck/top (positive up).

Board outline is in XY; rocker/stringer guides in XZ; transverse section curves use their own explicit local frame (typically local U=Y, V=Z, normal=+X). Foil components use the same global axes, with their own component frame and section frames. Frames are transforms, not implicit assumptions.

A local frame contains origin and a right-handed orthonormal basis or a quaternion + translation. Validate basis norm error, orthogonality and determinant. Do not silently normalize a badly formed persisted frame.

## 3. Persistent identity and curves

IDs are stable opaque strings (UUID recommended); unique within the document. IDs survive reorder, rename, edit and serialization. IDs must not be generated from array indices or face/edge numbers.

A curve record:
- `id`, `role`, `dimension` (2 or 3), `frame_id`, `closed`, `anchors[]`, `revision`.
- Each anchor: `id`, position, absolute incoming handle, absolute outgoing handle, continuity mode.
- Canonical continuity: `corner`, `smooth_aligned`, `symmetric`. Adapters map to implementation-specific enums.
- Corner: handles independent. SmoothAligned: collinear, opposite directions, lengths independent. Symmetric: collinear/opposite and equal lengths.
- Empty, duplicate IDs, non-finite values, dimension/frame mismatch, invalid closure and self-intersection are errors.

Editable cubic Bezier is the initial persisted curve primitive. A kernel may derive B-splines/NURBS from these curves; derived control points and knots are not a second source of truth unless explicitly promoted by a versioned edit.

## 4. Board domain

A `BoardShape` contains:

- `outline_curve_id`: closed planform XY curve.
- `rocker_curve_id` and optional `stringer_curve_id`: longitudinal XZ guide(s), with role and side/centreline semantics.
- `stations[]`: ordered section stations, each with stable ID, X coordinate, local frame, role, and independent deck/bottom section references or analytic profile parameters.
- `rail_definition`: semantic rail boundary/guide curve references and transition constraints; rail is not a duplicate freehand curve when it can be shared as a patch boundary.
- `nose` / `tail`: explicit end-condition records (shape family, source boundary refs, transition parameters, and optional local curves). Examples include round, square, pintail, swallow and squash; family names alone do not generate geometry.
- `mounts[]`: foil tracks, footstraps, handles, fins, inserts and user-defined mounts as parameterized features with frame and reference IDs.
- Optional laminate/stringer records may describe design intent and material layers, but must not alter geometric source curves implicitly.

Stations need not have equal control-point counts. The planform may have multiple outline intersections at an X near complex tails; station extraction must return valid intervals/branches and not assume one width value globally.

## 5. Foil domain

A `FoilAssembly` contains components with stable IDs and roles: main wing, stabilizer, mast, fuselage, optional winglets or other parts.

Each component stores:
- component-local frame and attachment transform;
- planform boundary curve(s), section stations and section local frames;
- section profile curves (editable anchors) and optional initial analytic profile metadata;
- sweep, span/dihedral, twist and chord parameters where these are explicit design parameters; derived values are labeled derived;
- shared boundaries and connection/attachment features (e.g. mast-to-wing, fuselage-to-wing, stabilizer mount);
- material/laminate intent as a separate optional record.

Foil stations are ordered along their declared span axis. No station or surface may rely on matching section anchor indices across stations. Board and foil geometry share curve/frame/feature identity semantics, but do not force board-specific fields onto foil components.

## 6. Surface recipes and continuity

Surface generation is a derived recipe referencing semantic curves and stations:
- Board patches: deck central, bottom central, port rail, starboard rail, nose transitions, tail transitions; optional local patches for recesses/inserts.
- Foil patches: pressure/suction surface, leading/trailing-edge closure, tip/winglet patches, component junctions.
- Shared boundary registry: one semantic boundary ID is referenced by adjacent patches; never create independent duplicate edges and hope sewing will repair them.
- Loft recipe declares direction, station order, curve orientation, parameterization strategy, interpolation/fairing settings, end conditions, seam correspondence and tolerances.

Continuity targets per boundary:
- **G0** positional agreement: mandatory at all intended joins.
- **G1** tangent-plane continuity: required only where a fair transition is specified (typically selected rails and foil junctions).
- **G2** curvature continuity: selective, optional and numerically validated; never promised globally.
- Deliberate hard edges are explicit boundary intent.

Loft algorithm contract:
1. Validate IDs, frames, curve closure, station order and section thickness.
2. Transform station curves into common component/product coordinates.
3. Establish consistent orientation and seam; reject ambiguous or reversed correspondence.
4. Use normalized arc-length/declared parameter sampling or a compatible B-spline basis; do **not** pair different control-point arrays by index.
5. Interpolate station parameters/geometry with a declared method; preserve design constraints and reject folds/crossings.
6. Build patches from shared boundaries; measure G0 and requested G1/G2 deviations.
7. Validate shell/solid, orientation, self-intersection where supported and tessellation error. Store diagnostics with the model revision.

## 7. Feature graph and revision invalidation

Each feature node has stable `id`, `type`, `inputs[]` (semantic IDs), parameters, output semantic IDs, revision and enabled state. Nodes form a directed acyclic graph (DAG). Source curves/stations are input features; lofts, patches, mount placements, measurements and meshes are derived.

Rules:
- Missing references and cycles are rejected.
- Recompute in topological order.
- A source edit invalidates dependent nodes and downstream cached artifacts only.
- Cache keys include source revisions, parameters, schema/kernel/algorithm version and relevant tolerances.
- Failed recomputation keeps the last valid result as a clearly stale preview; it must not silently mark stale geometry current.
- Kernel face/edge/vertex IDs are ephemeral derived topology, never persistent feature references.

## 8. Variants and provenance

A variant references a base revision and contains explicit deltas by semantic ID: parameter changes, curve edits, added/removed features, or feature overrides. The base model is immutable for that variant. Variant IDs and change IDs are stable; variants must be independently serializable and recomputable.

Imported scan, measurements and fitted geometry carry provenance (source ID, registration revision, fit method, date optional, and measured deviation). Provenance is metadata and does not replace editable design geometry.

## 9. Units, tolerances and computed properties

Tolerance budgets are separate, unit-labelled settings: sketch/curve fit, section thickness, patch boundary G0, G1 angular, optional G2 curvature, sewing, tessellation chordal/angular deviation, volume/centroid comparisons and manufacturing dimensions. No single global epsilon is used.

Suggested prototype starting budgets (review and calibrate; not manufacturing certification):
- curve/section fit: 0.05 mm;
- shared boundary G0: 0.05 mm;
- selected G1 join: 0.5 degrees;
- tessellation chord deviation: 0.5 mm;
- mesh angular deflection: 5 degrees.

Store computed properties as derived records with algorithm/version, model revision, units and error/quality indicator:
- volume (mm³ and litres), centroid (mm), surface area (mm²);
- board: volume and centroid for solid hull; optional wetted/planform areas clearly marked as condition-dependent;
- foil component/assembly: volume, centroid and component mass only when density/material inputs are provided;
- mesh and B-Rep validation results, self-intersection diagnostics, G0/G1/G2 measurements and tessellation error.
Mass, buoyancy and hydrodynamic performance are not inferred from geometry alone; record assumptions and inputs.

## 10. Illustrative versioned document shape

The following is a structural sketch, not a complete JSON Schema or a valid ready-to-import design. Exact field schemas, migration rules and requiredness are the next implementation work.

```json
{
  "document_type": "surfwing.shape",
  "schema_version": "0.1.0",
  "model_id": "model-uuid",
  "name": "Wingfoil board",
  "product_kind": "wingfoil_board",
  "units": { "length": "mm", "angle": "rad" },
  "coordinate_system": {
    "handedness": "right",
    "x": "nose_to_tail_positive_aft",
    "y": "centerline_to_starboard_positive",
    "z": "bottom_to_deck_positive_up"
  },
  "frames": [],
  "curves": [],
  "board": {
    "outline_curve_id": "outline-id",
    "rocker_curve_id": "rocker-id",
    "stringer_curve_id": "stringer-id",
    "stations": [],
    "rail_definition": {},
    "nose": {},
    "tail": {},
    "mounts": []
  },
  "foil_assembly": null,
  "feature_graph": { "nodes": [], "edges": [] },
  "surface_recipe": {},
  "tolerance_profile": {},
  "variants": [],
  "derived": {
    "source_revision": null,
    "volume_mm3": null,
    "centroid_mm": null,
    "validation": []
  }
}
```

For `product_kind=surfboard`, foil mounts/assembly may be absent. For `wingfoil_board`, mounts are explicit features. For `foil`, `board` is absent and `foil_assembly` is the root geometry. The schema must reject incompatible product-kind combinations.

## 11. Invariants and acceptance tests

| ID | Test | Acceptance |
|---|---|---|
| DM-001 | Schema round-trip | IDs, frames, handles, feature refs and variant deltas survive save/load with no identity changes |
| DM-002 | Unit conversion | 1 m → 1000 mm and 1 in → 25.4 mm; conversions happen once; unknown units rejected |
| DM-003 | Curve validity | finite values, unique IDs, valid closure; self-intersection errors include curve ID and location |
| DM-004 | Continuity | Corner permits discontinuity; SmoothAligned collinearity/opposed vectors within 1e-8 normalized angular residual; Symmetric also length equality |
| DM-005 | Frame validity | basis orthonormal and determinant +1 within 1e-9; malformed frames rejected, not silently repaired |
| DM-006 | Outline | closed, non-self-intersecting XY boundary; winding canonicalized only on import with an explicit report |
| DM-007 | Stations | ordered by longitudinal coordinate, unique IDs, station frames valid, no deck/bottom crossing above configured minimum thickness except declared tip singularities |
| DM-008 | Loft correspondence | unequal anchor counts and reversed curves are handled by declared orientation/parameter mapping; no index pairing |
| DM-009 | Surface joins | G0 gap ≤ configured tolerance; requested G1 angular deviation ≤ configured angle; G2 only where enabled and measured |
| DM-010 | Feature DAG | missing references/cycles rejected; edit invalidates exactly dependent cache descendants |
| DM-011 | Variant isolation | base revision hash unchanged; variant recomputes independently and references semantic IDs |
| DM-012 | Properties | volume positive, centroid inside/valid for solid; analytic fixture volume/centroid within 0.1% or declared numerical tolerance |
| DM-013 | Foil assembly | component frames/attachments round-trip; spanwise stations order and twist/sweep data are preserved |
| DM-014 | Regression | legacy BoardStation JSON and mesh output remain unchanged while schema migration is introduced |

## 12. Blockers / sequencing

- Issue #3: source-of-truth and Python/C++ integration decision remains open. This spec avoids choosing the implementation.
- Issue #7: section-loft path exists additively; JSON, longitudinal profile interpolation, integration and full test/CI verification remain pending.
- Draft PR #6: architecture proposal is still unmerged; review its contracts against this schema before implementation.

**Next milestone:** formal JSON Schema + serializer/validator + legacy import adapter, followed by round-trip fixtures for a surfboard, wingfoil board and multi-component foil. Do not build UI or kernel-specific topology around an unreviewed schema.
