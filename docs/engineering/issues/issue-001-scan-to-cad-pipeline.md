# Issue draft 001 — Scan-to-CAD pipeline

## Goal
Implement reproducible scan import, registration, section extraction and curve/surface reconstruction.

## Tasks
- Define supported scan formats and immutable source storage.
- Registration with transforms and fit statistics.
- Coverage and quality diagnostics.
- Section extraction and editable curve fitting.
- Deviation analysis and comparison report.
- Regression fixtures with expected metrics.

## Acceptance
Reproducible pipeline; raw input unchanged; scale and coordinate frame explicit; registration and reconstruction deviations reported; tests include poor-quality/incomplete scans.
