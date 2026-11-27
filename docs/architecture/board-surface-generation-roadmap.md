# Board surface generation roadmap

**Status:** architecture proposal; implementation not yet merged.
**Date:** 2026-11-25
**Scope:** transition from the current station-driven triangle mesh prototype to editable, production-oriented board geometry.

## 1. Verified current state

The current Python implementation in `src/board/geometry.py`:

- Defines longitudinal `BoardStation` values for width, thickness, bottom height, deck crown and bottom concave.
- Interpolates station fields using a local Catmull–Rom polynomial and clamps width between adjacent station widths.
- Samples a rounded perimeter from analytic trigonometric expressions.
- Connects sampled rings into triangles and caps nose/tail with center vertices.
- Checks edge-use count for watertightness and rejects non-positive volume.
- Exports OBJ and binary STL.

This is a useful deterministic mesh prototype. It is not a NURBS surface model, does not represent independently editable deck/bottom/rail curves, and does not provide B-Rep topology or feature history.

## 2. Target domain model

The editable source of truth should be kernel-independent and use millimetres internally.

### BoardDefinition
- Stable board ID, display name, schema version and units.
- Longitudinal coordinate convention and board symmetry plane.
- Named design curves and section stations.
- Parameter sets for outline, rocker, deck, bottom and rail design.
- Explicit construction constraints and validation status.

### DesignCurve
- Stable curve ID and semantic role: outline, rocker, deck section, bottom section, rail guide, foil track or local feature boundary.
- Ordered anchors with stable IDs, incoming/outgoing handles and continuity mode.
- Open/closed state, plane/frame and units.
- Curve revision and provenance.

### SectionStation
- Stable station ID and longitudinal X coordinate.
- Independent deck and bottom section curves in a local Y-Z plane.
- Optional rail tangent/curvature constraints.
- Explicit station role: nose, tail, max width, foil mount, handle/footstrap reference or user-defined.
- No implicit requirement that every station has identical control-point counts.

## 3. Surface strategy

Do not loft the entire board as one undifferentiated surface.

Build a controlled patch layout:
1. Deck central patch.
2. Bottom central patch.
3. Port and starboard rail patches.
4. Nose transition patches.
5. Tail transition patches.
6. Local inserts/recesses only as separate features when needed.

Use a shared boundary-curve registry. Adjacent patches must reference the same semantic boundary definition rather than independently fitted duplicate edges.

Continuity requirements:
- G0: positional closure at every shared boundary.
- G1: tangent-plane continuity where a fair deck/rail/bottom transition is required.
- G2: curvature continuity only where it materially improves shape fairness and is numerically stable.
- Deliberate hard edges must be explicit design intent, not accidental loft artifacts.

The first surface prototype should prioritize predictable G0 closure and controlled G1 rail transitions. Do not promise G2 globally.

## 4. Kernel boundary

The domain model must not store OCCT/Parasolid/ACIS face or edge indices as persistent design references.

Kernel adapters translate domain curves and surface definitions into kernel geometry. Kernel-generated faces, edges, p-curves and topology are derived artifacts with revision-scoped mappings.

The first OCCT spike should:
- Build individual tensor-product B-spline surface patches from explicit boundary/section data.
- Verify parameter orientation and shared-edge agreement.
- Sew patches into a shell.
- Check closure, orientation, self-intersection where supported, and shape validity.
- Export STEP and compare re-imported geometry.
- Record tolerances, failed cases and kernel version.

Keep the current triangle mesh generator as a preview/export path until the B-Rep path has reliable regression coverage.

## 5. Geometry validation gates

For every generated board:
- All coordinates finite.
- Positive thickness except explicitly declared tip singularities.
- Port/starboard symmetry within configured tolerance when symmetry is enabled.
- No unintended station ordering reversal.
- No self-crossing section curves.
- No collapsed or inverted surface patches.
- Shared boundaries agree within a declared sewing tolerance.
- Shell closure and orientation verified.
- Volume positive and within a plausible envelope.
- Tessellation deviation bounded against the analytic surfaces.

Every tolerance must be explicit and unit-aware. Avoid one global tolerance for sketch fitting, surface joining, STEP export and CAM.

## 6. Migration sequence

### B0 – Contract
Freeze the versioned domain schema for BoardDefinition, DesignCurve and SectionStation. Add schema migration and round-trip tests.

### B1 – Section editor
Create editable local Y-Z deck and bottom section curves. Add rail control and constraints. Keep sections independent; do not force matching control-point counts.

### B2 – Surface patch prototype
Implement one central deck and one central bottom patch between adjacent stations, then add port/starboard rails. Test G0 and selected G1 joins.

### B3 – Nose/tail closure
Add explicit end conditions and singularity handling. Reject invalid patches rather than silently generating degenerate triangles.

### B4 – OCCT adapter
Build B-spline surfaces, edges and wires; sew patches; validate shell; export/re-import STEP. Preserve domain IDs outside kernel topology.

### B5 – Preview and CAM
Tessellate B-Rep with bounded chordal/angular deflection. Generate CAM reference geometry only from validated model revisions. NC generation remains separately gated by machine profile and simulation.

## 7. Open decisions

- Which section representation is authoritative: cubic Bezier anchors, B-spline control polygons, or a hybrid editable Bezier-to-B-spline conversion?
- Whether board symmetry is enforced by mirrored geometry or by a symmetry constraint in the domain model.
- Which continuity levels are required for each patch boundary.
- Which OCCT version/build and license review are accepted for distribution.
- How local cutouts, foil tracks, inserts and recessed deck features enter the feature graph.
- Whether the UI is a Python desktop prototype or a native C++ application.

## 8. Explicit non-claims

This roadmap is not evidence that an OCCT adapter, NURBS patch generator, interactive editor, CAM surface pipeline or production-ready board solid already exists. Each requires implementation and measurable acceptance tests.
