# SurfWing CAD / wingshape_cad

Engineering working repository for SurfWing CAD, the parametric wingfoil-board and foil design/CAM project.

## Scope and development priorities

- Parametric board-shape CAD and editable outline/section curves.
- Control-point editing: stable anchors, two handles, corner/smooth continuity, insert/delete and undo/redo.
- Scan-to-CAD / reverse engineering: preserve raw scans, register, extract sections, fit editable curves and validate deviations.
- CAM/CNC workflow for the custom MOCNC, Estlcam and Arduino UNO; fail-closed NC checks and measured machine limits.
- Foil/board hydrodynamics: hydrostatics, first-order screening, CFD benchmarking and experimental validation.

## Machine target

- Custom MOCNC; Arduino UNO; Estlcam firmware and CAM (version TBD).
- Initial target is 3-axis XYZ; measured travel envelope, machine calibration and acceptance evidence are not yet recorded.

## Current prototype

The project bundle contains an early dependency-free board mesh generator (closed triangulated hull, OBJ and binary STL export), a restricted NC static validator, and first-order hydrodynamics calculations. These are prototypes, not a complete interactive CAD application, validated CAM engine, CFD solver, or machine-approved NC workflow.

## Safety

Generated NC must not be considered machine-approved because it parses or passes static checks. Confirm actual machine configuration, limits, E-stop, tool/stock/fixture setup, simulation and a controlled spindle-off air cut. Obtain operator approval before machining.

## Transfer status

Initial GitHub repository created; project import is being staged. Engineering review docs, test plans, issue drafts, code and example geometry should be added in follow-up commits and verified in GitHub.
