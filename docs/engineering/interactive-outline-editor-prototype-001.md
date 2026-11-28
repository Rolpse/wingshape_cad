# Interactive board-outline editor prototype

## Run locally

Open `prototype/board-outline-editor.html` in a modern browser. It is a standalone HTML file and has no package installation or server requirement.

## Current implementation

- Closed outline represented by one continuous cubic Bézier loop. The fill and visible perimeter use the same path; the fill is no longer a polygonal approximation.
- Geometry, anchors, handles, length and width are stored in millimetres. Changing nominal board length/width scales all anchor and handle coordinates proportionally.
- Every anchor has a stable ID, an incoming handle, an outgoing handle and a continuity mode:
  - **Corner:** independent handles.
  - **Smooth:** collinear, opposite handle vectors with independent lengths.
  - **Symmetric:** collinear, opposite handle vectors with equal lengths.
- Insertion uses an exact De Casteljau split at t=0.5 on the longest sampled-arc-length segment. This preserves that cubic segment up to floating-point precision.
- Deletion fits the two neighbouring cubic segments to one replacement cubic by least squares. The editor then calculates a conservative deviation upper bound using a global derivative/Lipschitz bound and an adaptive dense sample grid. The point is removed only when that upper bound is at or below the user-selected tolerance.
- If an insertion or deletion changes a neighbouring handle pair so that its stored Smooth/Symmetric mode is no longer true, that neighbour is explicitly changed to Corner. Geometry is not silently altered merely to retain an incorrect mode label.
- Numeric entry of anchor position and both handle coordinates is available in millimetres. If a numeric edit invalidates Smooth/Symmetric constraints, the mode is changed to Corner.
- Viewport navigation supports wheel zoom around the cursor, zoom buttons, Fit View, blank-canvas drag pan, and keyboard + / − / 0 shortcuts.
- Undo/redo, JSON import/export (mm), and start-geometry reset are available.

## Automated regression tests

Run:

```bash
node --test prototype/board-outline-editor.test.cjs
```

The Python test workflow also runs these tests using Node.js 24. The eight regression tests cover script parsing, the closed Bézier fill path, exact insertion preservation, tolerance-accepted and tolerance-rejected deletion, undo/redo, mm scaling, continuity-mode transitions, numeric coordinate entry and viewport navigation. These tests use a lightweight DOM stub; they do not replace manual browser testing.

## Current limitations

- The least-squares deletion fit approximates the two-piece curve with a single cubic. It is not a constrained NURBS refit; the reported conservative bound is for the parameter-matched curve pair used by this editor.
- Deletion and insertion are geometric operations, but the prototype still needs broader edge-case tests for very short spans, nearly coincident anchors and extreme handle magnitudes.
- The canvas has no pan/zoom, dimension/ruler annotations or precise keyboard coordinate entry yet.
- Cross-section view is a placeholder and is not generated from the board geometry.
- The editor is not yet connected to the Shape Document schema, board station model, analytic section kernel or 3D loft.
- No CAD kernel, editable deck/bottom/rail surfaces, STEP/STL export or CAM connection is present.
- No machine-approved CNC output is generated.

## Next implementation milestones

1. Add explicit width/length measurement annotations and stronger self-intersection / fold checks.
2. Connect outline geometry to the Shape Document schema and board station model.
3. Add editable transverse sections (deck, bottom, rail and thickness).
4. Build the first geometry-derived 3D preview and connect it to the existing loft prototype.
5. Add real-browser interaction tests and more edge-case geometry tests.
