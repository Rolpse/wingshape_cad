# Curve control-point editing contract (001)

## Purpose
Define editable curve behavior required for board outlines, rail profiles, rocker and foil geometry. This is a design contract; implementation and UI tests remain pending.

## Data model
Each anchor has a stable ID, coordinate, incoming and outgoing handle coordinates, and a continuity mode:
- **Corner**: incoming/outgoing tangents independent; sharp kink allowed.
- **Smooth**: handles collinear with anchor tangent direction; lengths may differ.
- **Symmetric**: handles collinear and equal length.

## Required interactions
- Add, select, move and delete control anchors; preserve IDs for unaffected anchors.
- Insert an anchor without changing original curve shape (exact split when supported, otherwise document approximation error).
- Delete anchor and locally refit, with deviation bound visible.
- Handle editing supports independently setting both handle points.
- Protect endpoints of open curves unless explicitly allowed.
- Undo/redo must restore exact geometry and selection state.

## Validation
Corner mode allows tangent discontinuity. Smooth tangents collinear within tolerance. Symmetric handles equal length within tolerance. Repeated edits must not create NaN/Inf. Test insertion shape preservation, deletion deviation, endpoint guard, mode transitions, stable IDs, serialization and undo/redo.

## Status
Contract documented. Interactive editor, curve kernel and automated acceptance tests are not implemented yet.
