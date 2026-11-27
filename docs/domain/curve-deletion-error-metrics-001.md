# Curve Deletion Error Metrics 001

**Status:** domain contract / measurement clarification. The current bounded cubic deletion prototype implements a symmetric sampled polyline-distance metric with a corrected combined-RMS denominator on PR #2. It is not a certified Hausdorff bound and is not merged to `main`.
**Repository:** `Rolpse/wingshape_cad`
**Scope:** deleting one interior anchor from two adjacent cubic Bezier segments and replacing them with one fitted cubic, without silently accepting excessive shape change.

## 1. Geometry and units

- All coordinates and distances are in canonical millimetres (mm).
- Source geometry (S) is the union of the two cubic segments adjacent to the deleted anchor.
- Fitted geometry (F) is the candidate replacement cubic.
- End anchors remain and retain stable IDs. The removed anchor ID is reported.
- Open-curve endpoints cannot be deleted by this operation.
- Distance is geometric point-to-curve distance, not same-parameter displacement: split/inverse-split changes local parameterization.

## 2. Sampled metric contract

For validation sample sets \(S_h=\{s_i\}_{i=1}^{N_S}\) and \(F_h=\{f_j\}_{j=1}^{N_F}\), use point-to-polyline projection distances:

\[
d_{S\to F}(s_i)=\min_{q\in \operatorname{polyline}(F_h)}\|s_i-q\|_2
\]

\[
d_{F\to S}(f_j)=\min_{q\in \operatorname{polyline}(S_h)}\|f_j-q\|_2
\]

Report separate directional RMS values:

\[
RMS_{S\to F}=\sqrt{\frac{\sum_i d_{S\to F}(s_i)^2}{N_S}},\quad
RMS_{F\to S}=\sqrt{\frac{\sum_j d_{F\to S}(f_j)^2}{N_F}}
\]

The combined symmetric RMS **must use the full sample count**:

\[
RMS_{sym}=\sqrt{\frac{\sum_i d_{S\to F}(s_i)^2+\sum_j d_{F\to S}(f_j)^2}{N_S+N_F}}
\]

When both sample sets have \(N\) points, the denominator is \(2N\), not \(N\). The symmetric maximum sampled deviation is:

\[
D_{max,sym}=\max(\max_i d_{S\to F}(s_i),\max_j d_{F\to S}(f_j))
\]

The fitter's symmetric least-squares score is the sum of the same two squared-distance sets; optimization must not silently switch to a one-direction score.

## 3. Tolerance and acceptance semantics

- The user tolerance `max_deviation_mm` is compared to \(D_{max,sym}\), not to RMS: accept iff \(D_{max,sym}\le max\_deviation\_mm\).
- A failed fit raises a tolerance exception carrying its complete report; the curve is not mutated.
- A report marked `accepted=false` must not be applied to the model.
- The RMS is descriptive and is not an alternate acceptance path.
- These metrics are **sampled estimates**. They are not a certified continuous Hausdorff-distance bound. Current prototype sampling is uniform in parameter space; this can under-sample high-curvature or poorly parameterized regions. Adaptive subdivision and a conservative geometric bound are a later validation gate.

## 4. Report contract

The operation result should report at least:

- removed `anchor_id`;
- `source_sample_count`, `fit_sample_count`, sampling strategy and resolution;
- `rms_source_to_fit_mm`, `rms_fit_to_source_mm`, `rms_symmetric_mm`;
- `max_source_to_fit_mm`, `max_fit_to_source_mm`, `max_symmetric_sampled_mm`;
- `tolerance_mm`, `accepted`, `exact_inverse_subdivision`;
- fit algorithm/version and optional iteration/diagnostic data.

The current PR #2 prototype report is narrower (combined RMS, max sampled deviation, tolerance, sample count, accepted flag and exact-inverse flag). Directional metrics and explicit sample metadata are follow-up requirements; do not claim they are already present.

## 5. Continuity and identity

- Preserve surviving anchor IDs and unrelated curve segments.
- Preserve endpoint positions exactly.
- The replacement cubic may update the outgoing handle of the left survivor and incoming handle of the right survivor.
- If the refit cannot retain the previous continuity constraint without changing the fitted geometry, downgrade only the affected endpoint mode to `corner` and include the downgrade in operation diagnostics. Never silently claim smoothness.
- Exact inverse de Casteljau removal reconstructs the parent segment control points when the removed anchor is a known exact split; the geometric report is still recorded and the surviving endpoint continuity modes are explicitly reviewed.

## 6. Failure cases

Reject with a typed/structured failure and no mutation for: missing anchor ID; endpoint deletion; non-finite or negative tolerance; too few samples; coincident surviving anchors; invalid/degenerate tangent fallback; fit not found or non-finite score; and maximum sampled deviation above tolerance.

## 7. Measurable acceptance tests

| ID | Test | Acceptance |
|---|---|---|
| CD-001 | Known directional-distance fixture: source→fit [0,2] mm; fit→source [1,3] mm | RMS source→fit \(=\sqrt2\) mm; RMS fit→source \(=\sqrt5\) mm; symmetric RMS \(=\sqrt{3.5}\) mm; symmetric maximum \(=3\) mm |
| CD-002 | Combined denominator | For equal sample counts, symmetric RMS equals square-root of all \(2N\) squared distances divided by \(2N\); never \(N\) |
| CD-003 | Exact split then removal | Stable endpoint IDs and exact parent control points restored within floating-point tolerance; report accepted for fixture tolerance |
| CD-004 | Threshold boundary | Accept when sampled max is exactly tolerance; reject when it exceeds tolerance by a known positive amount |
| CD-005 | Report completeness | Directional and combined RMS/max, counts, sampling method, tolerance, accepted, exact-inverse flag and units are present |
| CD-006 | No mutation on rejection | Serialized input curve is unchanged when tolerance or fit fails |
| CD-007 | Continuity | Unaffected anchors/segments unchanged; any endpoint continuity downgrade is explicit and reported |
| CD-008 | Degenerate inputs | Missing IDs, endpoints, coincident survivors, NaN/Inf, negative tolerance and insufficient sample count fail deterministically |

The known-distance metric fixture should exercise a pure metric helper independent of curve fitting so denominator regressions are unambiguous.

## 8. Implementation checkpoint

PR #2 head `d088ccc86c60f23f6dbf96e928086508d412ff4c` contains the corrected combined RMS denominator `2 * len(source)` in its general-fit path and also computes a combined symmetric RMS in its exact-inverse path. Its CI run #79 passed 48 tests. The branch is still open, not merged, and currently diverged from `main`; the code's sample strategy remains fixed uniform parameter sampling. Main commit `ffb78904b45ef72ce26bee46f4498a8dbedc80d8` only records the review finding in the engineering stability document.

This document is a specification and review checkpoint, not evidence that adaptive/certified deviation validation or the richer report has been implemented.
