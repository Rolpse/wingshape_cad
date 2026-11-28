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
- Exterior dimensions are calculated from the cubic Bézier extrema (derivative roots), not only anchor points. The starter profile is calibrated to an actual 1600 × 520 mm outside envelope.
- A preliminary integrity check rejects non-finite coordinates, adjacent coincident anchors and sampled self-intersections. The JSON export is disabled while the outline is invalid.
- Undo/redo, JSON import/export (mm), and start-geometry reset are available.

## Automated regression tests

Run:

```bash
node --test prototype/board-outline-editor.test.cjs
```

The Python test workflow also runs these tests using Node.js 24. The eleven Node.js regression tests cover script parsing, the closed Bézier fill path, exact insertion preservation, tolerance-accepted and tolerance-rejected deletion, undo/redo, mm scaling, continuity-mode transitions, numeric coordinate entry, viewport navigation, calibrated outside dimensions, self-intersection rejection and degenerate-anchor rejection. These tests use a lightweight DOM stub; they do not replace manual browser testing. The Python adapter suite covers Shape Document mapping, station-width sampling, guide scaling, immutability, invalid outlines, duplicate/non-finite input and a CLI end-to-end export. The current CI checkpoint contains 82 passing Python tests and 11 passing Node.js tests.

## Shape Document v0.1.0 adapter

The editor exports a standalone `surfwing.outline` JSON. Convert it to a complete, schema-validated board document from the repository root:

```bash
python -m src.domain.outline_editor_adapter surfwing-outline-mm.json \
  --template examples/domain/wingfoil-board-0.1.json \
  --output build/board-shape.json
```

The Python adapter:
- maps editor `(transverse, longitudinal)` coordinates to the canonical document `(longitudinal, transverse)` axes;
- transfers stable anchor IDs, both Bézier handles and Corner/Smooth/Symmetric continuity;
- samples the imported planform to recompute the template's section-station widths, moves the section frames, and scales rocker/stringer longitudinal coordinates;
- preserves the template's cross-section profiles and rocker/stringer Z values, clears cached derived properties, adds a warning, and validates the result with the existing Shape Document validator.

This is a planform-to-document bridge, not a complete board rebuild. The section profiles and rocker/stringer vertical shape remain template values and must be reviewed or edited before relying on 3D geometry or manufacturing output.

## Current limitations

- The least-squares deletion fit approximates the two-piece curve with a single cubic. It is not a constrained NURBS refit; the reported conservative bound is for the parameter-matched curve pair used by this editor.
- Deletion and insertion are geometric operations, but the prototype still needs broader edge-case tests for very short spans, nearly coincident anchors and extreme handle magnitudes.
- The self-intersection check uses a 64-step polyline approximation per cubic segment. It is an early screen, not an exact proof of curve simplicity; very narrow crossings and near-tangencies need stronger adaptive intersection testing.
- Cross-section view is a placeholder and is not generated from the board geometry.
- The browser editor does not yet write Shape Document JSON directly; the separate Python adapter performs that conversion. The editor and adapter are not yet connected to the analytic geometry kernel or 3D loft.
- No CAD kernel, editable deck/bottom/rail surfaces, STEP/STL export or CAM connection is present.
- No machine-approved CNC output is generated.

## Next implementation milestones

1. Improve self-intersection detection with adaptive curve subdivision and near-tangency tests.
2. Connect outline geometry to the Shape Document schema and board station model.
3. Add editable transverse sections (deck, bottom, rail and thickness).
4. Build the first geometry-derived 3D preview and connect it to the existing loft prototype.
5. Add real-browser interaction tests and more edge-case geometry tests.
