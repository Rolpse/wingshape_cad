# SurfWing CAD / wingshape_cad

Engineering working repository for SurfWing CAD, the parametric wingfoil-board and foil design/CAM project.

## Scope and development priorities

- Parametric board-shape CAD and editable outline/section curves.
- Control-point editing: stable anchors, two handles, corner/smooth/symmetric continuity, insert/delete and undo/redo.
- Scan-to-CAD / reverse engineering: preserve raw scans, register, extract sections, fit editable curves and validate deviations.
- CAM/CNC workflow for the custom MOCNC, Estlcam and Arduino UNO; fail-closed NC checks and measured machine limits.
- Foil/board hydrodynamics: hydrostatics, first-order screening, CFD benchmarking and experimental validation.

## Machine target

- Custom MOCNC; Arduino UNO; Estlcam firmware and CAM (version TBD).
- Initial target is 3-axis XYZ; measured travel envelope, machine calibration and acceptance evidence are not yet recorded.

## Current prototype

- Parametric board station model and closed triangle mesh; OBJ and binary STL export.
- Independent analytic transverse section kernel: flat, V, single/double concave, dome and standing-area profiles, with symmetric/asymmetric validation.
- Separate closed triangle-mesh loft for analytic sections, with a shared lateral sampling grid, nose/tail caps, longitudinal sampling and watertightness/positive-volume checks.\n- Provisional domain-document adapter for surfboard/wingfoil-board analytic station profiles.
- Restricted static NC validator (G00/G01 subset).
- First-order hydrofoil/board hydrodynamics screening calculations.

The transverse profile kernel and analytic section-loft mesh are additive paths. The new browser outline editor is still a separate prototype and is not yet connected to the geometry kernel, section model or 3D loft. These are prototypes, not a complete interactive CAD application, validated CAM engine, CFD solver, or machine-approved NC workflow.

## Imported source and tests

- Board mesh geometry: src/board/geometry.py; demo generator: src/board/generate_demo.py
- Transverse section model: src/board/sections.py
- Starter shape: examples/board/wingfoil-1600x520-starter.json
- CAM static validator: src/cam/estlcam_nc_validator.py
- Hydrodynamics calculations: src/hydrodynamics/performance.py
- Tests: tests/board, tests/cam, tests/hydrodynamics, tests/domain (75 Python tests); prototype/board-outline-editor.test.cjs (6 Node.js regression tests)
- Engineering contracts/reviews: docs/engineering and docs/board
- Acceptance plans: docs/quality
- Issue drafts: docs/engineering/issues

## Board geometry specifications

- [Board geometry generator 001](docs/board/board-geometry-generator-001.md)
- [Deck and bottom cross-sections DOM-004](docs/board/deck-bottom-cross-sections-004.md)
- [Control-point editing contract](docs/engineering/control-point-editing-contract-001.md)

## Domain model

- [SurfWing Shape Master Model 001](docs/domain/shape-master-model-001.md)\n- [Shape Document Schema 0.1.0 — implementation and limitations](docs/domain/shape-document-schema-implementation-001.md)\n- [JSON Schema Draft 2020-12](schemas/shape-document-0.1.0.schema.json)\n- Domain fixtures: `examples/domain/`

## Interactive editor prototype

- [Standalone board outline editor](prototype/board-outline-editor.html) — drag anchors and Bézier handles, toggle Corner/Smooth, exact midpoint insertion / approximate delete, undo/redo, JSON import/export.
- [Prototype status and limitations](docs/engineering/interactive-outline-editor-prototype-001.md)

## Interactive editor prototype

- [Standalone board outline editor](prototype/board-outline-editor.html) — closed Bézier outline, mm coordinates, two handles per anchor, exact anchor insertion, tolerance-checked deletion and JSON import/export.
- [Editor implementation notes](docs/engineering/interactive-outline-editor-prototype-001.md)

## Run

Build starter board mesh:
python -m src.board.generate_demo build/board-demo examples/board/wingfoil-1600x520-starter.json

Run tests:
python -m unittest discover -v

## Transfer completeness

Core source, example geometry, test suites and a subset of engineering/quality documentation have been imported. Original detailed CAM/CFD review documents, benchmark YAML files, CAM machine-profile/postprocessor documentation and some remaining supporting artifacts are still to be transferred and cross-checked.

## Safety

Generated NC must not be considered machine-approved because it parses or passes static checks. Confirm actual machine configuration, limits, E-stop, tool/stock/fixture setup, simulation and a controlled spindle-off air cut. Obtain operator approval before machining.
