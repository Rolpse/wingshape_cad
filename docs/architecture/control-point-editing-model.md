# Control-point editing model – Phase 1.2

**Status:** implementation completed in the separate C++20 kernel-independent prototype; integration into this repository is pending.
**Date:** 2026-11-25

## Purpose

Define the durable control-point contract for board outline, rocker and section curves. A control point is an editable anchor with two additional handles that define incoming and outgoing curve continuation. The model must support deliberate corners as well as smooth transitions.

## Implemented contract in the C++20 prototype

- A curve is an ordered list of anchors; vector position is ordering only and is not a persistent identity.
- Each anchor carries a stable semantic string ID, a 2D position, incoming and outgoing absolute handle positions, and a continuity mode.
- `Corner`: handles are independent; a tangent discontinuity is permitted.
- `SmoothAligned`: handles remain collinear and opposed; their lengths can differ.
- `Symmetric`: handles remain collinear and opposed with equal lengths.
- Anchor insertion uses de Casteljau subdivision and preserves the original cubic curve to floating-point precision.
- Anchor movement translates both handles by the same delta.
- Dragging one handle updates its opposite according to the selected continuity mode.
- Anchor deletion bridges the surviving neighbours using tangent directions; this is an approximation, not an exact inverse of insertion.
- Edits are applied to a candidate copy, validated, and committed atomically. Invalid edits leave the original curve unchanged.
- Empty and duplicate anchor IDs are rejected. Legacy anchors can receive deterministic IDs from the curve ID and a monotonic per-curve serial.

## Verified locally

The C++20 prototype builds with GCC 14.2.0. The core CTest target passes in both a normal build and an AddressSanitizer + UndefinedBehaviorSanitizer build. `git diff --check` is clean.

This is evidence for the isolated core operations only. It is not evidence that the Python application has been migrated, that a UI exists, or that undo/redo and file migration are implemented.

## Integration boundary

The existing repository contains a Python board/CAM/hydrodynamics prototype. The C++20 sketch core is currently a separate implementation. Do not replace or delete the Python implementation as part of this phase.

Recommended integration sequence:

1. Preserve the Python prototype and its existing tests.
2. Import the C++ core into a clearly separated `cpp/` or `native/` module.
3. Establish a versioned interchange schema for curve IDs, anchor IDs, coordinates, handles, continuity modes, units and curve closure.
4. Add round-trip tests between the interchange schema and both implementations before binding the C++ core into the UI.
5. Only then decide whether Python remains orchestration/analysis tooling or whether the native core becomes the source of truth.

## Open decisions

- Which implementation is the long-term source of truth: Python prototype, C++ core, or a staged hybrid?
- What stable file schema/version is used for curve persistence and migration?
- Should dimensional/geometric constraints be solved in the core or in a separate sketch-solver module?
- What undo/redo command model is required for multi-anchor edits?
- Which UI toolkit will own pointer capture, snapping, selection and drag previews?

## Downstream impact

- **Board outline / rocker / sections:** all use the same anchor/handle semantics and stable IDs.
- **Surface lofting:** section curves can be referenced by semantic IDs without depending on kernel edge indices.
- **Feature graph:** edit operations become versioned commands; derived geometry is invalidated from changed curve revisions.
- **Scan fitting:** fitted curves must retain source-scan provenance while emitting normal editable anchors.
- **CAM:** toolpaths and machining boundaries must reference semantic regions/curve revisions, never anchor vector indices.
- **Persistence:** schema migration must preserve IDs across reorder, insertion, deletion and round trips.

## Exit criteria for the next phase

- A versioned curve interchange schema exists.
- Python and C++ round-trip the same test curves within a declared tolerance.
- Undo/redo restores geometry and IDs exactly.
- UI drag tests cover Corner, SmoothAligned and Symmetric modes.
- Insert/delete regression tests verify geometric deviation bounds.
