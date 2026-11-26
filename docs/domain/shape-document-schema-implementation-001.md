# Shape Document Schema 0.1.0 — implementation record

**Status:** structural JSON Schema committed; provisional Python semantic validator/adapter; latest CI passes 75 tests. Domain acceptance remains partial.  
**Repository:** `Rolpse/wingshape_cad`  
**Schema:** [shape-document-0.1.0.schema.json](../../schemas/shape-document-0.1.0.schema.json)

## Files

- `schemas/shape-document-0.1.0.schema.json`: JSON Schema Draft 2020-12. Strict objects, canonical units, product-kind constraints, IDs, frames, curves/anchors/handles, board stations and analytic profiles, mounts, foil components and span axes, feature graph, surface recipe, tolerances, variants and derived metadata.
- `src/domain/shape_document.py`: stdlib semantic validator, JSON load/save entry points, length conversion, field-level variant application and legacy BoardStation import.\n- `src/board/document_loft.py`: provisional adapter that converts analytic board station profiles into `BoardCrossSection` and calls the section loft.
- `examples/domain/surfboard-0.1.json`: surfboard structural fixture.
- `examples/domain/wingfoil-board-0.1.json`: wingfoil-board fixture with foil-track mount and a width variant.
- `examples/domain/foil-assembly-0.1.json`: multi-component main wing, fuselage, stabilizer and mast with declared span axes and station frames.
- `tests/domain/test_shape_document.py`: schema, semantic validation, round-trip, units, IDs, frames, outline self-intersection, profile crossing/symmetry, references, feature cycles, variants, foil attachment cycle and legacy import tests.

## Canonical contract

- Persist length in **mm**, angles in **rad**, right-handed axes **X aft, Y starboard, Z up**. Imported units convert once.
- IDs are stable semantic IDs, never array indexes or kernel topology numbers.
- Frames persist origin and three basis axes. Validation checks unit-length, mutual orthogonality and determinant +1; malformed frames are rejected, not normalized silently.
- Curve anchors persist absolute position plus incoming/outgoing handles and `corner`, `smooth_aligned` or `symmetric` continuity. Smooth modes require opposed collinear handle vectors; symmetric mode also requires equal handle length.
- Board stations are strictly ordered in X and carry width/thickness/bottom baseline plus independent analytic deck and bottom profile descriptions. Symmetry is declared or defaults to symmetric.
- Foil component `span_axis` is explicit (`x`, `y` or `z`); station values are ordered along that axis. Attachments are translation plus unit quaternion.
- Feature graph input IDs resolve to semantic entities or feature nodes; edges and node inputs are cycle-checked.
- Variants v0.1 support field-level `set`/`remove` deltas to a deep copy. Base documents are not mutated by applying a variant.

## Legacy adapter

`import_legacy_board_json` accepts the current station-based JSON format and creates a deterministic-ID v0.1 document from the canonicalized source payload. It reconstructs a simple symmetric planform outline, rocker and deck stringer from station values, maps deck crown to a dome profile and bottom concave to a single-concave profile, and stores the exact source JSON under `board.legacy_source`.

**This is a migration approximation, not an exact geometric conversion.** The old generator remains the authority for the old file format and its mesh output. The adapter never replaces or modifies `generate_board_mesh`.

## Current implemented checks

- Structural JSON Schema (when the optional `jsonschema` package is installed; CI installs it for tests).
- Canonical document type/version/units/axes.
- Finite values; semantic ID uniqueness.
- Frame orthonormality/right-handedness.
- Curve dimensions, handle continuity, closed 2D polygon zero-area/edge and self-intersection checks.
- Board curve references, station order, positive width/thickness, analytic deck-bottom thickness samples, profile symmetry and profile-curve references.
- Foil component/station/frame/section references, ordered stations, unit quaternions, parent attachment cycles.
- Feature graph references and cycles; surface boundary/patch references.
- Variant target IDs and immutable identity-field protection.
- Legacy source retention and deterministic generated IDs.

## Not yet implemented (explicitly not accepted as complete)

- Curve-level editing operations, constraints or NURBS conversion.
- G0/G1/G2 surface join measurements; `surface_recipe` is declarative only.
- Full outline validation for spline curves: self-intersection currently checks anchor polygon edges, not cubic segments.
- Self-intersection tests for 3D curves/surfaces or mesh fold-over.
- Numerical volume/centroid computation, mass, buoyancy or hydrostatics; derived records are metadata only.
- Feature-cache dependency invalidation/recompute.
- Variant add/delete entity operations, list-index edits, base-revision enforcement or recompute. v0.1 field changes only.
- Exact mapping from legacy triangle mesh to new section profiles; legacy source is preserved and import warns.
- Curve-backed section profiles, measured G0/G1/G2, fold-over/self-intersection validation, integration into legacy mesh generator, interactive editor, CAM/CFD kernels.
- Python/C++ interchange/runtime integration until Issue #3 is decided.

## Acceptance coverage

| Requirement | v0.1 status |
|---|---|
| DM-001 ID/frame/handle round-trip | test written |
| DM-002 mm/m/in conversion | test written |
| DM-003 finite values and 2D polygon self-intersection | implemented for polygon anchors; test written |
| DM-004 handle continuity | implemented; dedicated regression coverage still to add |
| DM-005 frame validity | test written |
| DM-006 closed outline polygon validity | test written; spline-level validation pending |
| DM-007 station order/profile thickness | test written |
| DM-008 loft correspondence | pending loft milestone |
| DM-009 measured G0/G1/G2 | pending surface kernel |
| DM-010 missing refs/cycles | feature cycle test written; cache invalidation pending |
| DM-011 variant isolation | field delta test written; base revision policy pending |
| DM-012 volume/centroid | pending geometry kernel |
| DM-013 foil station/frame/attachment | fixture and tests written |
| DM-014 legacy compatibility | adapter/source-preservation test; legacy mesh regression remains in existing tests |

## Gate

No CI result is claimed in this record. The workflow has been updated to install `jsonschema` and run `python -m unittest discover -v`; verify the Actions run triggered by these commits before considering the milestone accepted. Issue #3 and Issue #7 remain separate blockers for native interoperability and integrated loft/profile persistence.


## Analytic board loft adapter checkpoint (2026-11-27)

- `src/board/document_loft.py` consumes validated v0.1 surfboard/wingfoil-board documents with analytic deck/bottom profiles and converts station data to `BoardCrossSection`.
- `generate_section_loft_mesh` now supports `longitudinal_samples_per_interval`: it interpolates width and evaluated deck/bottom samples on a common normalized lateral grid, rather than pairing profile control-point arrays. Default `1` preserves station-only ring density.
- Test coverage includes both board product fixtures, asymmetric V profile, curve-backed-profile rejection, densification ring count, positive signed volume and invalid sampling.
- CI: [run 45913190338](https://github.com/Rolpse/wingshape_cad/actions/runs/45913190338), **75 tests passed** on commit `9dcd91bc3eb34dc326c4974a7557ea8b8ebef41c`.
- This remains an additive mesh prototype; no spline/B-Rep generation or geometric fold/self-intersection validation is claimed.


## Next gate / blockers

The next geometry-model step is **curve-backed transverse profiles and continuity/fold validation**. It is not safe to invent a second curve identity/evaluator now:

- Editable Bezier curve model is still open PR [#2](../../pull/2); its branch CI is green, but mergeability/review state is unresolved.
- Surface architecture is still draft PR [#6](../../pull/6); no accepted production patch/B-Rep kernel or G0/G1/G2 measurement implementation.
- Python/C++ boundary remains unresolved in [Issue #3](../../issues/3).
- [Issue #7](../../issues/7) tracks profile-curve integration, legacy-generator integration and fold/self-intersection validation.

The schema and additive analytic loft are implemented/tested; pause further schema research until these dependencies move or a concrete issue changes the contract.
