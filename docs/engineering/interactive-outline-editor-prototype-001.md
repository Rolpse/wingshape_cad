# Interactive board-outline editor prototype

## Run locally

Open `prototype/board-outline-editor.html` in a modern browser. It is a standalone HTML file and has no package installation or server requirement.

## Current controls

- Move an anchor by dragging its white/orange marker.
- Drag the two gold handles to control each Bézier anchor's incoming/outgoing tangent.
- Cycle the selected anchor through Corner → Smooth → Symmetric. Smooth handles remain collinear; Symmetric keeps the two handle lengths equal.
- Add an approximate anchor or delete an interior anchor.
- Undo/redo, import/export JSON, and adjust nominal board length/width.

## Limitations / known defects to address

- The outline display is a polygonal fill plus Bézier curves, so the fill does not exactly follow the curve yet.
- Anchor insertion now uses a mathematically exact De Casteljau split at t=0.5 (within floating-point arithmetic).
- Anchor deletion does not refit with a tolerance bound.
- Symmetric mode can now be toggled in the editor.
- The board dimensions are stored as metadata and do not yet scale the canvas geometry.
- Undo/redo history snapshots are taken on pointer-down, so a drag gesture creates a single undo entry.
- Cross-section view is a placeholder, not a geometry-derived section.
- No shape-document schema adapter, 3D loft, CAD kernel, STEP/STL or CAM connection.

## Next implementation milestones

1. Correct closed outline representation and segment joining.
2. Implement exact De Casteljau split for adding anchors, with tests.
3. Add symmetric continuity control and robust handle normalization.
4. Add dimension-based coordinate mapping (mm) and viewport zoom/pan.
5. Add section editing and board station model adapter.
6. Connect the editor to the shape document and geometry/loft pipeline.
7. Add automated browser acceptance tests.
