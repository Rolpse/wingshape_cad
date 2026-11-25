# Bezier control-point model 001

## Implemented on feature/bezier-control-point-model

- Open cubic Bezier curves in 2D or 3D.
- Stable unique anchor IDs.
- Each anchor stores position plus absolute incoming and outgoing handle points.
- Corner, Smooth and Symmetric continuity modes.
- Moving an anchor translates both handles.
- Handle editing applies continuity constraints for Smooth/Symmetric modes.
- Exact curve insertion by de Casteljau subdivision.
- JSON-compatible serialization.

## Important behavior

An exact split changes handle lengths at the adjacent anchors. If an adjacent anchor was Symmetric, it is downgraded to Smooth to preserve exact curve geometry and tangent continuity. Corner anchors remain independent.

The original `delete_anchor` remains a simple straight-chord approximation for compatibility. New code should use `delete_anchor_bounded(anchor_id, max_deviation, samples_per_segment=80)`. It fits a replacement cubic with the surviving endpoint tangent directions, returns a `DeletionReport` (RMS and maximum sampled deviation), and raises `CurveFitToleranceError` if the tolerance is exceeded. Endpoints of open curves are protected.

The tolerance is currently a approximate symmetric distance between uniformly sampled source and fitted polylines, not a mathematically certified Hausdorff-distance bound. The fit optimizes the two handle lengths with a deterministic coarse grid and pattern refinement. The RMS and maximum values are sampled geometric-distance estimates, not exact analytic extrema. For production board/CAM geometry, adaptive subdivision and a geometric distance bound are still required. The joined endpoint anchors are set to Corner mode because the refit may not preserve their prior opposite handles.

## Not yet implemented

- Bounded-error sampled curve refit on deletion (first implementation; see limitations below).
- Closed curves and periodic seams.
- Multi-segment spline fitting, curvature combs and fairing.
- Adaptive geometric error bounds, interactive viewport, hit-testing, drag handles, snapping and undo/redo.
- Board outline/section integration and persistent project document schema.

## Acceptance tests

The test suite additionally checks bounded deletion on an exact split and rejection when the sampled deviation exceeds tolerance. CI workflow is configured to run python -m unittest discover -v; a successful GitHub Actions run has not yet been verified.
