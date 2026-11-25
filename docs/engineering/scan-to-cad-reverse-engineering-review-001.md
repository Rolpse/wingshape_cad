# Scan-to-CAD / reverse-engineering review 001

## Workflow
1. Acquire and archive original scan immutable, with metadata, units and capture notes.
2. Validate coverage and scale; identify noisy, occluded and duplicated regions.
3. Register scans into documented coordinates; retain transforms and residuals.
4. Produce denoised/decimated working copies only.
5. Extract longitudinal/transverse sections and fit editable curves.
6. Build parameterized model from sections and constraints.
7. Compare reconstructed surfaces against scan with signed and absolute deviation maps.
8. Validate volume, dimensions, smoothness, symmetry and local feature preservation.
9. Export neutral and mesh formats; record tolerance and export checks.

## Required metrics
Registration residual (RMS and robust percentile), surface coverage, point density, section-fit RMS/max deviation, reconstructed-vs-scan deviation percentiles, dimensions/volume delta and topology status.

## Tool strategy
Keep scan handling modular and optional. CloudCompare can be used externally; verify license and distribution obligations before bundling. Open3D can be evaluated as an optional dependency. Record versions, licenses, reproducible settings and sample datasets.

## Risks / gaps
No scan input or registration pipeline exists yet. Coordinate-frame ambiguity, scale drift, smoothing away rails/concaves, overfit curves and missing coverage are critical. No acceptance tests have been run.

## Next tasks
- Define scan interchange and coordinate frame.
- Implement registration/quality report.
- Section extraction and editable curve fitting.
- Surface deviation analysis and sample dataset tests.
