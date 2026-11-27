# Editable curve integration and surface-core stabilization 001

**Status:** engineering stabilization plan, not implementation acceptance
**Repository:** `Rolpse/wingshape_cad`
**Updated:** 2026-11-27
**Scope:** stabilize editable curve semantics, document interoperability, curve-backed sections, and controlled surface generation before CAM.

## Verified baseline

- Main has a versioned shape document schema 0.1.0, provisional validator, and analytic board document-to-loft adapter.
- Main CI run 45913190338 passed 75 tests on commit 9dcd91bc3eb34dc326c4974a7557ea8b8ebef41c. This does not cover the open Bezier PR or production surface kernel.
- PR #2 (`feature/bezier-control-point-model`) contains Python editable cubic Bezier curves: stable anchor IDs, absolute incoming/outgoing handles, Corner/Smooth/Symmetric constraints, de Casteljau insertion, bounded deletion fit, serialization and tests. PR remains open; current connector reports mergeability false. Treat its branch as candidate, not integrated.
- PR #6 is a draft architecture proposal. It specifies kernel-neutral semantics and a patch surface layout; it does not implement a B-rep surface kernel.
- Issue #3 (Python/C++ boundary) is unresolved. Issue #5 tracks editable section curves and controlled patches. Issue #7 tracks curve profile integration and mesh fold/self-intersection checks.

## Geometry invariants (must be enforced at model boundary)

1. **Coordinates:** finite values only; canonical mm; curve dimension fixed (2D or 3D); IDs stable and unique within curve; no reliance on list indices for persisted identity.
2. **Handle storage:** absolute handle points, documented consistently across serialization. A handle may be zero-length only when the operation/continuity mode permits it; degenerate endpoint tangent cases must produce explicit diagnostic status.
3. **Continuity modes:** Corner permits independent handles. SmoothAligned requires opposing collinear handle vectors (tangent alignment, not curvature continuity). Symmetric additionally requires equal handle lengths. Define numerical tolerances in units/scale-aware terms; avoid arbitrary dimensionless comparisons on raw coordinates.
4. **Edit atomicity:** operations run on a candidate copy; validation succeeds before committing. Failure must not mutate original curve or IDs.
5. **Insertion:** de Casteljau split must preserve the original curve within floating point error. Report/record any continuity-mode downgrade (e.g. Symmetric to SmoothAligned) required to preserve exact geometry; do not silently relabel.
6. **Deletion/refit:** tolerance is user-specified and in mm. Report max/RMS geometric deviation, method and sampling density. Current PR fit is sampled and is not a certified Hausdorff bound; it must not be labeled mathematically bounded without adaptive error certification. If acceptance is not met, refuse deletion.
7. **Persistence:** serialize schema version, curve ID, dimension, closure state (currently open curves only), anchor IDs, positions, handles, continuity. Round-trip preserves IDs and geometry. Migration must not invent unstable IDs on every load.
8. **Undo/redo:** command snapshots or reversible operations restore exact serialized state, including IDs and continuity modes; undo/redo itself must not re-fit geometry.

## Stabilization test matrix

| ID | Test | Required outcome |
|---|---|---|
| C-01 | Non-finite coordinates, wrong dimensions, empty/duplicate IDs | Reject with deterministic diagnostics |
| C-02 | Smooth/Symmetric handle alignment, zero/near-zero handles, endpoint anchors | Enforce or explicitly classify tangent-degenerate cases |
| C-03 | Insert at t near 0, 0.5, 1 (excluding endpoints), random t; 2D and 3D | Same curve before/after split; stable new ID; no duplicate IDs |
| C-04 | Insert adjacent to Symmetric anchor | Geometry preserved; mode downgrade documented and test asserts result |
| C-05 | Delete exact prior split and delete arbitrary point | Exact inverse split is near machine precision; arbitrary refit emits RMS/max; tolerance violation refuses operation |
| C-06 | Curve reversal, segment order, serialization/reload | Shape and semantics stable; IDs persist; tangent direction handled correctly |
| C-07 | Random/property-based curves with scale variation (1e-3 to 1e6 mm) | No scale-dependent false continuity or silent numerical corruption |
| C-08 | Atomic failure, unknown ID, invalid edit, undo/redo | Original unchanged; redo/undo exact serialization |
| C-09 | Python schema ↔ candidate curve model round trip | No ID, units, handle or continuity loss; declared numerical tolerance |
| C-10 | Board outline spline validation | Test actual cubic segments for intersections, not anchor polygon alone; reject invalid closed outlines |
| C-11 | Curve-backed deck/bottom profile | Profile curve IDs resolve; profile sampling handles different segment/anchor counts; no index pairing |
| C-12 | Loft transitions across stations | Interpolate evaluated geometry on normalized lateral coordinates; check thickness, orientation, folds, and degeneracies |
| C-13 | Surface patch boundaries | Shared semantic boundary curve is reused; G0 gap measured; G1 only where requested and tangent angle measured; chine/corner boundaries explicitly discontinuous |
| C-14 | Surface core output | Valid shell/topology, orientation, closed volume and self-intersection diagnostics; invalid fixtures are rejected, not repaired silently |
| C-15 | Tessellation regression | Chordal/angular error measured against surface; positive volume and watertightness verified; preserve legacy mesh fixture |
| C-16 | Performance reproducibility | Deterministic fixtures; record runtime, peak memory, algorithm/tolerance/version; establish thresholds only after baseline |

## Surface model contract

- Semantic patch roles: deck central, bottom central, port rail, starboard rail, nose closure, tail closure, optional local patches (tracks/recesses) only as explicit features.
- Each patch has a stable patch ID, source boundary IDs, surface definition/revision, parameterization and validation report. Never store kernel face/edge index as design identity.
- Boundaries carry intended continuity: G0 required at joins; G1 requested only for fair joins; G2 selectively where justified. Chine and other sharp transitions are intentional G0-only joins.
- Sewing tolerance is distinct from curve fitting, STEP exchange and mesh chordal tolerance. Reports include all tolerances and units; avoid one global tolerance.
- Derived B-rep and mesh artifacts are caches, reproducible from semantic source and feature revisions.

## Dependency and sequencing gates

**Gate A — editable curve candidate accepted:** PR #2 review/merge decision; branch tests re-run against current main; resolve mergeability; correct limitations in deletion refit and scale-sensitive validation; test matrix C-01–C-09.
**Gate B — interchange decision:** Issue #3 chooses Python-first, native C++ module, or staged migration. Define ownership/versioned adapters and Python↔C++ round-trip; no UI binds directly to kernel topology.
**Gate C — curve-backed section profiles:** add curve references and evaluator adapter; integrate with document loft; C-10–C-12; maintain legacy station generator behavior.
**Gate D — surface prototype:** patch boundary contract and kernel adapter, then C-13–C-15. Prototype first on baseline and deliberately degenerate fixtures; no production/STEP/CAM claims until validation.
**Gate E — CAM unlock:** only after surface geometry is validated, closed, and exports/tessellation have quantified error. Then define blank/tool models, toolpaths, postprocessor and collision/rest-material tests.

## Prioritized work (do not claim completed until evidence exists)

1. **P0:** PR #2 branch compatibility, fresh CI and review; examine curve numerical/continuity defects; capture exact test outcomes.
2. **P0:** make curve deletion deviation status honest: sampled estimate vs certified bound, refuse if sampled maximum exceeds tolerance, use adaptive refinement for higher confidence; add scale/degenerate tangent tests.
3. **P0:** settle interchange/source-of-truth boundary in Issue #3 and curve schema adapter.
4. **P1:** cubic segment-level outline/profile intersection checks; deterministic robust predicates/tolerance strategy.
5. **P1:** curve-backed deck/bottom profile evaluator and station transition regression.
6. **P1:** patch boundary/continuity validator with measured G0 gap and G1 angle diagnostics.
7. **P2:** optional OCCT prototype after fixtures/contracts; report B-rep validity, sewing, positive volume, STEP round-trip, tessellation error, performance. Kernel selection remains provisional until measured.

## Risk register

| Risk | Severity | Mitigation / exit evidence |
|---|---|---|
| Sampled deletion tolerance presented as hard bound | High | Label estimator; adaptive/certified bound or conservative refusal; test against dense independent sampling |
| Curve anchor-polygon test misses cubic self-intersections | High | Segment-level curve intersection tests with adversarial fixtures |
| Python/C++ duplicate models drift | High | Versioned neutral schema and round-trip tests before UI binding |
| Profile point-index pairing twists surfaces | High | Evaluate each profile on common normalized coordinate grid; test unequal anchor counts/asymmetric profiles |
| Patch seams or rail/nose singularities | High | Shared semantic boundary, measured continuity, degeneracy fixtures, B-rep validity report |
| Kernel topology IDs unstable across rebuild | High | Semantic IDs only; kernel topology treated as transient mapped output |
| Tolerance conflation causes geometry loss or sewing failure | High | Separate units/settings and report measured error per stage |
| Legacy generator regression | Medium | Additive integration; preserve fixtures and full existing CI |

## Completion evidence

This document is a plan/specification. It does **not** claim that the tests above were executed, that PR #2 was merged, that a surface kernel exists, or that CAM is unblocked. Record commits, test logs, measured errors and review decisions in the relevant issues/PRs when work is performed.


## Code-review finding — PR #2 bounded-deletion RMS metric

**Finding (confirmed by source inspection; not runtime-tested):** in `delete_anchor_bounded()`, the general-fit path's `errors()` score sums squared distances from both source samples to fitted polyline and fitted samples to source polyline (2N distances), but the report computes `rms = sqrt(best[0] / len(source))` (N denominator). This makes the reported RMS larger by a factor of sqrt(2) than the RMS over the combined symmetric sample set. It is conservative numerically but inconsistent with the stated metric and with the exact-subdivision path, which calculates RMS over source samples only.

**Required correction:** define the metric explicitly and use one convention consistently. Recommended: report separate source-to-fit RMS and fit-to-source RMS, plus their combined RMS (denominator 2N) and maximum symmetric sampled deviation; include sampling method/density. Do not silently use one directional RMS in the exact path and symmetric RMS in the general path. Add a test with a known distance distribution to catch denominator errors. This is a review observation, not a patch or test result.

**Additional review priority:** the sampled deviation is still not a certified Hausdorff bound; independently dense/adaptive sampling must be used for validation, and scale/degenerate tangent tests remain outstanding.
