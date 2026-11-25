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

- Parametric board station model and closed triangle mesh; OBJ and binary STL export.
- Restricted static NC validator (G00/G01 subset).
- First-order hydrofoil/board hydrodynamics screening calculations.

These are prototypes, not a complete interactive CAD application, validated CAM engine, CFD solver, or machine-approved NC workflow.

## Imported source and tests

- Board geometry: src/board/geometry.py; demo generator: src/board/generate_demo.py
- Starter shape: examples/board/wingfoil-1600x520-starter.json
- CAM static validator: src/cam/estlcam_nc_validator.py
- Hydrodynamics calculations: src/hydrodynamics/performance.py
- Tests: tests/board, tests/cam, tests/hydrodynamics
- Engineering contracts/reviews: docs/engineering and docs/board
- Acceptance plans: docs/quality
- Issue drafts: docs/engineering/issues

## Run

Build starter board mesh:
python -m src.board.generate_demo build/board-demo examples/board/wingfoil-1600x520-starter.json

Run tests:
python -m unittest discover -v

## Transfer completeness

Core source, example geometry, test suites and a subset of engineering/quality documentation have been imported. Original detailed CAM/CFD review documents, benchmark YAML files, CAM machine-profile/postprocessor documentation and some remaining supporting artifacts are still to be transferred and cross-checked.

## Safety

Generated NC must not be considered machine-approved because it parses or passes static checks. Confirm actual machine configuration, limits, E-stop, tool/stock/fixture setup, simulation and a controlled spindle-off air cut. Obtain operator approval before machining.
