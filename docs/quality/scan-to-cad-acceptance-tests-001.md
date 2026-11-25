# Scan-to-CAD acceptance tests (001)

**Status: NOT RUN — no scan dataset or pipeline implementation supplied.**

| ID | Acceptance condition | Evidence |
|---|---|---|
| SC-01 | Original scan remains byte-identical | source hash before/after |
| SC-02 | Scale and coordinate frame recorded | report/config |
| SC-03 | Registration reports RMS and percentile residuals | registration report |
| SC-04 | Coverage/occlusion identified | coverage map |
| SC-05 | Sections extracted at reproducible locations | section files |
| SC-06 | Editable curves serialize and reload | round-trip test |
| SC-07 | Surface deviation reports RMS, max and percentiles | map/report |
| SC-08 | Board dimensions and volume delta documented | metrics |
| SC-09 | Invalid/incomplete scan fails with diagnostic | automated test |
| SC-10 | Exports open in independent viewer | evidence/logs |

Quantitative thresholds must be agreed against scan accuracy and manufacturing tolerances before test execution.
