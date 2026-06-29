---
name: parametric-cad-generation
description: Design 3D-printable parametric objects and enclosures in Python using CadQuery or build123d from natural-language requirements. Use when Codex needs to turn a user's dimensions and feature requests into an editable CAD script, iterate on cutouts or mounting features, validate the generated Python, prepare STL/STEP-ready output for mechanical parts, or plan backend-aware multicolor print handoffs.
---

# Parametric CAD Generation

Generate and iterate Python CAD scripts for printable parts. Prefer the bundled CLI for repeatable brief validation, prompt generation, and starter CadQuery scaffolds.

When the `cad` / CAD Skills / text-to-cad skill is available, use it as the default clean-CAD generation and review layer for new mechanical parts. Keep this skill responsible for the 3D-print-specific orchestration around design contracts, mesh preservation, Bambu handoff, and printer-native output.

If the request involves multicolor output, printer-native `3MF`, AMS/MMU workflows, or slicer-specific handoff requirements, read `references/multicolor-backends.md` before committing to a deliverable or color strategy. Read `references/multicolor-brief-fields.md` when you need a canonical checklist for capturing multicolor intent in the brief.

## Workflow
1. Capture the design brief from the user's request.
Default to millimeters.
Default to text-to-cad's build123d/STEP-first workflow for clean mechanical CAD when that skill is installed.
Use this repo's local `cadquery` renderer for rectangular enclosure starter scripts, for backwards compatibility, or when text-to-cad is unavailable.
Use rectangular enclosure assumptions only when the user is describing a box, housing, case, or cavity-based part.
2. Capture manufacturing intent before writing CAD when color, assembly, bed splitting, or printer-native output matters.
At minimum, resolve:
- target printer or slicer/backend
- whether AMS/MMU or multi-material hardware exists
- color count
- desired final artifact: geometry only (`STL`/`STEP`) or printer-native project (`3MF`)
- whether the result should print assembled in-place, as separate inserts, side-by-side parts, split across plates, or a hybrid
Use `references/multicolor-brief-fields.md` as the canonical field checklist when the request is multicolor, slicer-specific, or printer-specific.
3. Write or update a structured brief JSON before writing CAD code when the requirements are non-trivial.
4. For multi-part enclosures, make print orientation and assembled orientation explicit before modeling.
State which faces are exterior, which faces mate, and whether supports are acceptable.
5. Choose the color strategy intentionally before adding style features.
Use one of:
- in-place multicolor bodies for backend-proven same-part color regions
- separate inserts or appliques when the slicer/backend is fragile
- side-by-side accent parts when color should not be fused into the main object
- hybrid workflows when some details should print in-place and others should remain separate
6. Run the bundled CLI to validate the brief and, when applicable, render a starter CadQuery script.
7. If the renderer is too narrow for the requested shape, use the bundled prompt generator as the base for a custom Python CAD script.
If text-to-cad is available, prefer handing the clean-CAD portion to that workflow instead of stretching this repo's starter renderer beyond rectangular enclosure cases.
8. Syntax-check generated Python locally.
9. If `cadquery` or `build123d` is installed, run the script and export STEP as the primary artifact, then STL/3MF sidecars as needed.
If CAD dependencies are missing, still deliver the script and state that geometry export was not executed.
10. For enclosure lids or mating parts, validate the seated assembly with a boolean interference check, not just a visual preview.
11. When multicolor output, printer-native output, or a printer-specific multi-part split is requested, generate the manufacturing handoff as deliberately as the CAD.
Do not stop at geometry if the user asked for a printer-ready result or gave a specific printer/slicer target.
12. Validate the final artifact at the right layer:
- geometry build success
- fit/interference for mating parts
- source-triangle accounting when a source mesh must be preserved
- body separation and non-overlap for color regions
- backend export success
- final project structure when `3MF` or slicer-native output is requested
- fallback `3MF` package structure and transforms against the target slicer's accepted shape, not just triangle counts
- target slicer CLI import/info check when available, especially for Bambu `3MF`
13. For dimension-change iterations, recompute dependent geometry before regenerating exports.
Check derived slopes, landings, connector or fastener positions, rib/vent positions, bed fit, and clearance assertions instead of changing only the headline dimension.
14. Iterate by editing parameters or helper functions instead of rewriting the whole file.

## Decision Rules
- Parameterize every dimension that may change.
- Treat parameter edits as dependency edits: update all derived features that depend on changed width, depth, height, or printer bed constraints.
- Use relative references and named workplanes instead of brittle magic coordinates.
- Keep the origin convention explicit in comments: centered in X and Y, `Z=0` at the bottom unless there is a good reason not to.
- Prefer printable defaults: 2-3 mm enclosure walls, conservative cut depths, and no unnecessary support-heavy geometry.
- For styled variants, preserve the internal fit first and restyle the exterior shell second.
- For lids, never assume preview orientation and print orientation are the same; model both intentionally.
- When a lid uses a lip or insert feature, validate the true seated position against fillets, chamfers, and lead-ins on the mating base.
- Treat multicolor, bed splitting, and printer-specific output as manufacturing problems, not just geometry problems.
- Plain `STL` does not carry reliable color intent. Do not describe it as a printer-ready multicolor artifact.
- Prefer printer-native or slicer-ready `3MF` when the user names a target printer/slicer and the design is multi-part, split across the bed, multicolor, or intended as a ready-to-open print project.
- For clean CAD generated through text-to-cad, validate the STEP first with its inspection tooling before handing STL/3MF sidecars to this repo's Bambu workflow.
- For Bambu A1/A-series targets, create a Bambu handoff spec by default for multi-part or bed-split designs; attempt a Bambu-authored `3MF` when the local backend is available, otherwise provide standard `3MF` plate files plus the handoff spec and state the limitation.
- For single-material Bambu fallback `3MF` files, prefer neutral direct-mesh 3MF structure: mesh objects directly in `3D/3dmodel.model` resources, build items pointing directly at those objects, and no partial Bambu project metadata.
- Use Bambu-style component wrappers and `3D/Objects/object_N.model` only when patching or deriving from a known-good Studio-authored template.
- Do not trust Bambu `--export-3mf` success or ZIP integrity alone. Prefer the artifact that Bambu Studio `--info` reports with dimensions, facets, manifold status, and volume.
- Keep final output folders unambiguous. Remove or clearly quarantine `_neutral`, `_bambu_cli`, all-parts bundles, and other diagnostic exports unless the user explicitly wants them.
- Printer-ready generators should build temporary meshes from the current parametric geometry, not from previously exported STL intermediates. This prevents stale geometry after late parameter edits.
- Make assembly STEP export optional for print-plate generation. It is useful for CAD review but can be slow or hang, and it should not block STL/3MF deliverables when the user asked for printer-ready plates.
- For functional ramps, wedges, clips, and other load/contact parts, report changed functional ratios such as slope after major dimension edits. Warn when a compact revision materially increases print or use risk.
- Avoid perfectly flush coplanar color regions by default unless the target slicer/backend is already proven to preserve them.
- For unknown or fragile slicers, prefer slightly proud or debossed color features, separate inserts, or separate accent parts.
- Keep in-place multicolor bodies as distinct non-overlapping solids with clean adjacency.
- If the printer-native result depends on a slicer-specific project format, use that slicer as the final serializer instead of inventing a clean-room format unless the repo already has a validated writer.
- For Bambu-style one-click output, prefer `Bambu Studio` as the final serializer and use a handoff spec plus seed-template workflow when available.
- When the user requires an existing artistic mesh to be retained, use the mesh-preserved workflow instead of a clean parametric redraw: partition source triangles across the fixed body and moving parts, select movable skins from the front-visible surface rather than a through-volume slice, add generated shell/backing/tray geometry, and validate source-triangle accounting, slicer-closed mesh health, and functional-core mesh health before slicer review.
- Keep comments short and practical. Document units and coordinate assumptions.
- Preserve the existing script across refinements when possible.

## Multicolor Deliverables

When the user asks for multicolor, printer-native output, or gives a specific printer/slicer for a multi-part print, do not assume one export format is enough. Pick the deliverable that matches the real goal:

- `Geometry only`: export aligned `STL` and `STEP` bodies per color region or per part.
- `Slicer handoff`: export separate aligned solids plus a machine-readable handoff spec that records grouping, filaments, and plate intent.
- `Printer-native project`: produce the slicer-native `3MF` or project file only after the handoff has been validated against the real backend.
- `Plate-ready geometry package`: when the slicer backend cannot be automated, export one standard `3MF` per build plate plus a handoff spec explaining plate intent.

If the user wants "Bambu Handy style" one-click printing, that means a Bambu-native project, not just colored geometry.

## Multicolor Verification

For multicolor parts, verify all of the following when possible:

- color bodies do not overlap in volume unless they are intentionally boolean-unioned into one material region
- in-place color bodies remain aligned in the assembled orientation
- separate inserts still fit after styling changes
- the backend project maps each intended body or part to the expected filament
- the final `3MF` contains the expected part or object structure for the target slicer, not just the expected colors in metadata

If a supposedly successful export looks wrong in the slicer, inspect the project structure directly instead of trusting the export status.

## Backend Notes

- Prefer generic `STL`/`STEP` output when the user only needs printable geometry.
- When the target is a specific slicer or printer ecosystem, make that backend explicit in the brief and handoff, even for single-color parts.
- If the active repo already provides printer-specific tooling, use it instead of re-inventing export conventions.
- If CAD Skills / text-to-cad is available, use it for clean STEP/build123d generation and CAD Explorer review rather than duplicating those generic capabilities here.
- For Bambu workflows, expect raw geometry imports to be only a handoff layer. Use Bambu Studio or validated Bambu automation to produce the final visible multicolor `3MF`.
- For single-color Bambu jobs split into multiple parts or plates, still produce the Bambu handoff spec and a `3MF` deliverable when possible; AMS is not required for printer-native project value.

## Bundled CLI

Set once:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PARAMETRIC_CAD_CLI="$CODEX_HOME/skills/parametric-cad-generation/scripts/cad_flow.py"
```

Create a starter brief:

```bash
python3 "$PARAMETRIC_CAD_CLI" init-brief --output brief.json
```

Validate a brief:

```bash
python3 "$PARAMETRIC_CAD_CLI" validate brief.json
```

Generate an LLM prompt from the brief:

```bash
python3 "$PARAMETRIC_CAD_CLI" prompt brief.json --output prompt.md
```

Render a starter CadQuery script for rectangular enclosure-style parts:

```bash
python3 "$PARAMETRIC_CAD_CLI" render brief.json --output enclosure.py
```

Syntax-check the resulting script even when CAD packages are missing:

```bash
python3 -m py_compile enclosure.py
```

Fit-check an enclosure-style script that exposes `build_base()` and `build_lid()` plus
either `get_lid_seat_height()`, `LID_SEAT_Z`, or `BASE_OUTER_HEIGHT` and `LID_LIP_DEPTH`:

```bash
python3 -m llm_to_3dprint.cli check-fit enclosure.py
```

## Reference Map
- `references/brief-schema.md`: brief fields, defaults, and coordinate conventions.
- `references/multicolor-backends.md`: multicolor strategy selection, backend-specific handoff rules, and final artifact verification.
- `references/multicolor-brief-fields.md`: canonical multicolor brief fields and example handoff structure.
- `scripts/cad_flow.py`: reusable CLI for brief init, validation, prompt generation, and CadQuery starter rendering.
