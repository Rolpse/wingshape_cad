# Kernel evaluation for SurfWing CAD

**Status:** provisional architecture decision / validation gate  
**Research date:** 2026-11-25  
**Repository:** `Rolpse/wingshape_cad`  
**Scope:** editable board curves and section profiles → patch surfaces → closed B-Rep → STEP / bounded tessellation

## Decision summary

**Use Open CASCADE Technology (OCCT) as the first kernel candidate for a small, measured prototype; do not yet hard-lock the production kernel.** The current architecture already calls for a kernel adapter and OCCT sewing/validity/STEP tests. This is now a real implementation boundary, but the project has not run a kernel comparison on SurfWing geometry.

Keep the durable source of truth **kernel-independent**: versioned `BoardDefinition`, `DesignCurve`, `SectionStation`, semantic boundary IDs, constraints, and a feature graph. The OCCT B-Rep and tessellated mesh are derived representations. Never persist OCCT face/edge indices as design identity.

OCCT is the best initial fit because the current project is Python-first and needs freeform surface patches, loft, sewing, validity checks, offset/Boolean operations, STEP exchange, and mesh export without an SDK purchase. This is a provisional engineering recommendation, not evidence of OCCT superiority or of a completed kernel adapter.

## Repository facts that affect this decision

- `main` currently generates a station-driven closed triangle mesh in `src/board/geometry.py`; it does not produce NURBS/B-Rep surfaces or editable deck/bottom/rail patches.
- `src/board/sections.py` is an analytic transverse section prototype; Issue #7 says it is **not yet connected** to `generate_board_mesh`.
- Draft PR #6 defines a kernel-neutral curve/domain contract and patch surface roadmap. Its B4 step specifically proposes an OCCT adapter, sewing, validity checks and STEP round-trip.
- Issue #5 already requires stable semantic IDs, controlled deck/bottom/rail patches, G0/G1 checks and OCCT shell validation.
- The repository currently has no root `LICENSE` file. Project distribution licensing must be decided separately before bundling any kernel.
- The Python test workflow on PR #2's current head passed: 48 tests, `python -m unittest discover -v`, Python 3.12.16, GitHub Actions run #29. This validates the current Python prototype only; no kernel test has been run.

## Comparison matrix

Qualitative fit is for SurfWing's current scope, not a general vendor ranking. Robustness cannot be ranked from documentation/marketing alone; the same fixtures and tolerances must be benchmarked.

| Option | Surface/loft, B-Rep, topology | Offset / Boolean / validation | Integration & ecosystem | Licensing | SurfWing fit |
|---|---|---|---|---|---|
| **OCCT** | Native B-Rep; freeform curves/surfaces; documented loft through wires and vertex end sections; sewing and shape checks | Has offset, pipe, thick-solid, sewing and Boolean APIs; BRepCheck plus repair/analysis tools. APIs and capabilities are documented, but operation success on our boards is untested | C++ kernel; Python binding options are third-party (pythonOCC/pyOCCT); suitable for a Python prototype but version/build/GUI packaging must be tested | LGPL 2.1 with OCCT exception; distribution obligations and exception need legal review | **Best first prototype**; open and feature-matched |
| **Parasolid** | Mature commercial B-Rep/freeform and direct modeling; vendor documents >900 functions and convergent/facet modeling | Strong vendor claims and broad industrial adoption; specific loft/offset/Boolean failure rates on our test geometry unknown | Commercial C++ SDK, documentation/support and Parasolid XT interoperability across many applications; vendor trial for commercial developers | Proprietary commercial SDK; terms/quote required; no public price verified | **Strong technical alternative** if OCCT fails measurable gates or budget permits |
| **ACIS (Spatial)** | Commercial B-Rep modeler; supports direct and history-based workflows and topology tracking/attributes | Vendor documents Boolean, blending, direct editing, thickening, offset and validity analysis; project-specific robustness unknown | Commercial C++ SDK; optional meshing/interop add-ons; evaluation request available | Proprietary commercial SDK; terms/quote required; no public price verified | **Strong alternative**, but cost and dependency require business case |
| **CGAL** | Excellent computational-geometry and polygon-mesh algorithms; current official package docs focus on mesh/polygon processing, not a complete NURBS B-Rep feature-CAD workflow. No current official general NURBS B-Rep package was verified in this research | Mesh Boolean/corefinement can use exact predicates and exact constructions; strict manifold-triangulated-volume input/output requirements apply | C++ template library; powerful for mesh checks, repair, reconstruction, triangulation and exact geometric algorithms; not the simplest primary CAD solid kernel for patch-based board design | Package-specific: LGPL for core/support, GPL for most higher-level algorithms; commercial option. Check each used package | **Complementary toolbox**, especially for mesh robustness/reconstruction; not primary kernel candidate |
| **NURBS / B-spline only** | Smooth parametric curves/surfaces, suitable for editable board shape and patch definitions | No topological solid model, sewing, solid validity, feature tracking or Boolean engine by itself | Representation/algorithm layer, not a drop-in kernel. Must pair with topology/operations or implement them | Depends on implementation/library | **Use as geometry representation where appropriate, not as kernel decision** |
| **Hybrid feature graph + B-Rep + mesh** | Semantic design features and curves define shape; B-Rep provides exact surfaces/topology; mesh is derived for preview/CAM | Kernel ops are delegated; mesh validation may use CGAL or project-specific checks | Architecture independent of any vendor kernel; adapter boundary and revision-scoped mapping | Depends on selected kernel; domain schema itself can remain project-owned | **Required architecture regardless of kernel** |

### Evidence notes

- OCCT documents `BRepOffsetAPI_ThruSections` for lofts, including section-wire compatibility/orientation checks and smoothing/ruled options. Its B-Rep validation (`BRepCheck_Analyzer`) checks topology, wire closure/self-intersection, orientation and shell closure. It also exposes offset, pipe, thick-solid, sewing and related modeling APIs. See the official links below.
- Siemens describes Parasolid as a commercial geometric modeler with freeform surface/sheet, direct and solid modeling, tessellation, convergent modeling and broad XT interoperability. The public trial is offered for commercial application developers; pricing is not published in the pages reviewed.
- Spatial describes ACIS as a commercial modeler with direct/history-based modeling, Boolean, blend, thickening, offset, topology tracking and validity analysis. These are vendor capability statements, not independent benchmark results.
- CGAL's Boolean mesh package requires manifold triangulated volumes; its docs explain that exact predicates alone do not prevent self-intersection from rounded intersection constructions, and recommend exact constructions for consecutive operations. Its package licensing is mixed.
- Topological naming is a general parametric CAD risk: faces/edges may be renamed after upstream changes. SurfWing must use semantic design IDs and explicit feature/boundary mappings, not raw kernel indices.

## Recommended architecture consequences

1. **Domain layer (authoritative):** versioned `BoardDefinition`, `DesignCurve`, `SectionStation`, symmetry and continuity constraints, feature IDs, shared semantic boundaries. Persist millimetres explicitly; stable IDs are not array indices.
2. **Feature graph:** each operation stores a stable `feature_id`, input semantic IDs, parameter/schema version, dependencies, output roles and revision. Recompute/invalidate downstream nodes from changes. Store kernel-specific artifacts as disposable derived cache.
3. **Kernel interface:** expose only project-owned operations, e.g. `build_surface_patches`, `sew_shell`, `validate_shape`, `boolean`, `offset`, `export_step`, `tessellate`. The adapter returns structured diagnostics and tolerance metadata; it does not leak kernel types into domain/UI/CAM code.
4. **First implementation:** prototype OCCT through a pinned Python binding in an isolated optional environment. If binding/package issues or performance block it, move the adapter to C++/pybind11 without changing the domain schema. Do not make the current Python CI require OCCT yet.
5. **Patch layout:** deck central, bottom central, port/starboard rail, nose/tail closures, and local features. Adjacent patches share the same boundary-curve definition. G0 required; G1 only on specified fair joins; G2 selective.
6. **Output:** B-Rep/STEP is the validated geometric source for future CAM preparation; mesh is derived with explicit chordal/angular error. Existing OBJ/STL station generator remains unchanged until regression and parity gates pass.
7. **Licensing:** add/choose the repository license separately; perform OCCT LGPL exception review and check binding/add-on licenses before distribution.

## Prototype validation questions and test fixtures

The prototype should produce a machine-readable report: kernel/build/version, operation, tolerance settings, pass/fail, validity diagnostics, geometric error, runtime and memory. No “robust” conclusion without repeatable results.

| ID | Fixture / operation | Questions / acceptance evidence |
|---|---|---|
| K1 | Baseline board: 1600 × 520 mm starter plus several length/width/thickness variations | Can the deck/bottom/rail patch set be built without degenerate faces? Positive volume? Stable parameterization? |
| K2 | Adjacent patch boundaries | Are shared curves truly reused? G0 gap ≤ **0.05 mm** candidate; G1 tangent mismatch ≤ **0.5°** candidate on specified smooth joins; report exceptions for intentional chine/corner |
| K3 | Longitudinal loft: sections with different anchor counts, asymmetric profiles, reordered/near-duplicate sections, nose/tail vertex tips | Does loft twist, collapse or self-intersect? Are wire orientations/compatibility explicit? Reject invalid cases with clear errors |
| K4 | Offset rail curves/surfaces: positive/negative offsets; tight concave radii; offset near local radius; rail tuck | Does offset fail, self-intersect, create slivers or change topology? Record the failure threshold and require explicit failure/repair, not silent geometry |
| K5 | Boolean cut/add: foil track recess, insert pocket, deck recess, drain/cutout; overlapping, near-tangent, coplanar and disjoint cutters | Can operations create valid results consistently? Are edge cases reproducible? Check topology, volume, non-manifold output and error diagnostics |
| K6 | Edit/rebuild: insert/delete section, move rocker/width/rail guide, change symmetry, change upstream feature | Do semantic IDs survive? Does feature graph invalidate only downstream outputs? No persistent references to kernel face/edge numbers |
| K7 | STEP export/import regression | Geometry, dimensions, names/units and topology remain within stated tolerance. Verify supported schema/version; do not assume full AP242 coverage from the presence of a STEP writer |
| K8 | Tessellation from validated B-Rep | Measured chordal deviation and angular error; closed mesh and positive volume; no CAM boundary derived from invalid shape |
| K9 | Binding/runtime/deployment | Pin kernel and binding versions; test Python 3.12 on CI and target desktop OS; verify headless import/build, GUI viewer compatibility, license notices and packaging |
| K10 | Performance | Run at least 30 deterministic variations; report p50/p95 rebuild and boolean time, peak memory, failure rate. Establish targets after baseline, not from vendor claims |

**Initial tolerance targets are test hypotheses only.** K2 values are suggested starting thresholds for surfacing tests, not approved manufacturing tolerances. Tune the sewing tolerance separately from curve fitting, STEP transfer and tessellation error; never use a single global tolerance.

## Decision gate

Proceed with the OCCT spike only after the kernel-neutral section/patch inputs and representative fixtures are defined. Promote OCCT from candidate to production decision only if:

- K1–K8 pass on a representative board set (including deliberately invalid/degenerate fixtures that must be rejected);
- tolerances and STEP round-trip deviations are measured and recorded;
- K9 is viable for the intended desktop deployment;
- K10 meets interactive expectations or a C++ adapter is justified;
- project and dependency licenses are reviewed.

If any critical gate fails, run the same fixture set against Parasolid/ACIS evaluation SDKs before changing the architecture. CGAL remains an optional mesh-processing/robustness component, not a second primary B-Rep kernel.

## Official and primary sources

- [OCCT license and exception](https://www.occt3d.com/dev/doc/overview/html/index.html#license)
- [OCCT loft API — BRepOffsetAPI_ThruSections](https://www.occt3d.com/dev/doc/refman/html/class_b_rep_offset_a_p_i___thru_sections.html)
- [OCCT modeling algorithms — offsets, sewing, thick solids, loft](https://occt3d.com/dev/doc/refman/html/package_brepoffsetapi.html)
- [OCCT B-Rep validity checker](https://occt3d.com/dev/doc/refman/html/class_b_rep_check___analyzer.html)
- [OCCT STEP guide](https://occt3d.com/dev/doc/overview/html/occt_user_guides__step.html)
- [Siemens Parasolid overview](https://www.siemens.com/en-gb/products/plm-components/parasolid/)
- [Siemens Parasolid SDK options](https://www.siemens.com/en-us/products/plm-components/parasolid/3d-modeling-sdk/)
- [Parasolid commercial developer evaluation](https://resources.sw.siemens.com/en-GB/parasolid-free-evaluation/)
- [Spatial ACIS modeler](https://www.spatial.com/solutions/3d-modeling/3d-acis-modeler)
- [CGAL Boolean operations on meshes](https://doc.cgal.org/latest/PMP_Boolean_operations/)
- [CGAL exact-computation FAQ](https://www.cgal.org/FAQ.html)
- [CGAL licensing](https://www.cgal.org/license.html)
- [pyOCCT Python bindings](https://github.com/trelau/pyOCCT)
- [FreeCAD documentation: topological naming problem](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Topological_naming_problem.md)

