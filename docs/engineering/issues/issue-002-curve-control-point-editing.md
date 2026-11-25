# Issue draft 002 — Editable control points and handles

Implement anchor insertion/removal/movement, two handles per anchor, Corner/Smooth/Symmetric modes, endpoint guards, stable IDs, curve-preserving insertion, bounded local refit on deletion, serialization, undo/redo and tests.

Acceptance: corner mode creates sharp junctions; smooth/symmetric satisfy constraints; insertion error is measured; deletion error bounded; invalid geometry rejected; state survives undo/redo and save/reload.
