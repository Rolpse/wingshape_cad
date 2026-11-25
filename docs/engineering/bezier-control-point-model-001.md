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

Deleting an interior anchor is currently a documented straight-chord approximation and resets the two joined anchors to Corner mode. It does not yet provide a maximum-deviation guarantee. Endpoints of open curves are protected.

## Not yet implemented

- Bounded-error least-squares curve refit on deletion.
- Closed curves and periodic seams.
- Multi-segment spline fitting, curvature combs and fairing.
- Interactive viewport, hit-testing, drag handles, snapping and undo/redo.
- Board outline/section integration and persistent project document schema.

## Acceptance tests

The test suite checks 2D/3D operation, exact split equivalence at 101 parameter samples, continuity constraints, stable IDs, endpoint protection and serialization. CI workflow runs python -m unittest discover -v.
