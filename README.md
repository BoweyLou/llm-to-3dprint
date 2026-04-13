# LLM to 3D Print

This repo turns the "LLM -> Python CAD -> STL/STEP" workflow into a usable starter kit.

It does three practical things:

1. Stores a design brief in a structured JSON format.
2. Builds a strong prompt you can hand to an LLM.
3. Renders a starter CadQuery script for rectangular enclosure-style parts.

It now also includes a Bambu Studio handoff layer for workflows where the final deliverable
needs to be a printer-ready `.3mf` project rather than raw geometry alone.

The current code is intentionally narrow in one place: the automatic renderer targets rectangular enclosures and similar cavity-based parts first. The surrounding brief, validation, and prompting workflow is general enough to extend to other object families.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

If you want to execute generated CAD scripts locally, also install the CAD extra:

```bash
pip install -e ".[cad]"
```

Create a starter brief:

```bash
python3 -m llm_to_3dprint.cli init-brief --output examples/rectangular_enclosure.json
```

Validate the brief:

```bash
python3 -m llm_to_3dprint.cli validate examples/rectangular_enclosure.json
```

Generate an LLM prompt from the brief:

```bash
python3 -m llm_to_3dprint.cli prompt examples/rectangular_enclosure.json --output generated/enclosure_prompt.md
```

Render a starter CadQuery script:

```bash
python3 -m llm_to_3dprint.cli render examples/rectangular_enclosure.json --output generated/enclosure.py
```

If `cadquery` is installed, run the generated script to export STL and STEP files into `generated/output/`.

For enclosure-style scripts that expose `build_base()` and `build_lid()`, you can also
check whether a seated lid interferes with the base:

```bash
python3 -m llm_to_3dprint.cli check-fit generated/my_enclosure.py
```

The fit checker looks for one of these seat-height conventions:

- `get_lid_seat_height()`
- `LID_SEAT_Z`
- `BASE_OUTER_HEIGHT` and `LID_LIP_DEPTH`

Create a starter Bambu Studio handoff for an A1 hybrid two-color project:

```bash
python3 -m llm_to_3dprint.cli init-bambu-project --output examples/bambu_a1_hybrid_project.json
```

Validate the Bambu handoff:

```bash
python3 -m llm_to_3dprint.cli validate-bambu-project examples/bambu_a1_hybrid_project.json
```

Render an import/save plan that Codex, a human, or a future MCP wrapper can follow:

```bash
python3 -m llm_to_3dprint.cli bambu-handoff examples/bambu_a1_hybrid_project.json --output generated/bambu_handoff.md
```

Probe the local Bambu Studio install:

```bash
python3 -m llm_to_3dprint.cli bambu-probe
```

Write the Bambu CLI assemble-list JSON directly:

```bash
python3 -m llm_to_3dprint.cli bambu-build-cli examples/bambu_a1_hybrid_project.json --output generated/bambu_assemble.json
```

Attempt a Studio-backed `.3mf` export:

```bash
python3 -m llm_to_3dprint.cli bambu-export-cli examples/bambu_a1_hybrid_project.json --output generated/out.3mf
```

The CLI export path is real, but Bambu Studio assemble-list import only accepts STL/OBJ inputs for grouped multipart parts. STEP files need a sibling STL/OBJ fallback. On this machine, BambuStudio 02.05.00.66 currently crashes during export before writing the `.3mf`, so the command reports that failure instead of pretending success.

If you want the working local fallback, use the GUI-backed exporter instead:

```bash
python3 -m llm_to_3dprint.cli bambu-export-gui examples/bambu_a1_hybrid_project.json --output generated/out.3mf
```

That GUI path is currently scoped to the grouped in-place multicolor object. On this Mac, it is the reliable way to produce the multicolor lid project, but it intentionally leaves side-by-side accents and separate base parts outside the saved `.3mf`. When the handoff spec defines a valid `seed_template_3mf`, the GUI exporter now prefers that seed-template path up front instead of rebuilding the grouped import tree, so the saved `.3mf` preserves the separate-object multicolor structure that Bambu Studio renders correctly. The multipart merge confirmation is currently handled with a calibrated screen click because the affirmative control is not exposed cleanly through macOS accessibility.

If Hammerspoon is installed, the GUI path can now prefer it for the merge-confirmation click and fall back to the existing Swift helper if Hammerspoon is unavailable or not ready:

```bash
python3 -m llm_to_3dprint.cli bambu-export-gui examples/bambu_a1_hybrid_project.json --click-backend auto
```

Inspect the local Bambu Studio runtime before attempting automation:

```bash
python3 -m llm_to_3dprint.cli bambu-probe
```

If Hammerspoon is installed, bootstrap `hs.ipc` once so the repo can call the bundled Bambu GUI actions by name:

```bash
python3 -m llm_to_3dprint.cli bambu-setup-hammerspoon
```

Write the exact `assemble_list.json` that Bambu Studio CLI expects:

```bash
python3 -m llm_to_3dprint.cli bambu-build-cli examples/bambu_a1_hybrid_project.json --output generated/bambu_assemble_list.json
```

Attempt a Studio CLI export to a printer-facing `.3mf`:

```bash
python3 -m llm_to_3dprint.cli bambu-export-cli examples/bambu_a1_hybrid_project.json --assemble-output generated/bambu_assemble_list.json
```

The CLI command is honest about failure. It reports the exact command, resolved presets,
whether the `.3mf` was actually written, and any matching Bambu Studio crash report.

If you already have a Studio-authored `.3mf`, the patch command is the most reliable way to
restore multicolor metadata without re-importing the geometry from scratch:

```bash
python3 -m llm_to_3dprint.cli bambu-patch-3mf examples/bambu_a1_hybrid_project.json generated/output/bambu_gui_test.3mf --output generated/output/bambu_gui_test_patched.3mf
```

That patch path is currently validated for single-nozzle Studio projects where the imported
object names or source filenames still line up with the Bambu handoff spec.

If you already maintain a known-good Studio project template for a printer/profile, you can
patch that seed template directly into a fresh output:

```bash
python3 -m llm_to_3dprint.cli bambu-apply-template examples/bambu_a1_hybrid_project.json --output generated/output/retro_from_template.3mf
```

That template-backed path is the intended next step for robust Codex automation. It keeps
Bambu Studio in the serialization loop while avoiding repeated fragile import/rebuild steps.

You can now validate or capture a Studio-authored seed template explicitly:

```bash
python3 -m llm_to_3dprint.cli bambu-check-template examples/bambu_a1_hybrid_project.json
python3 -m llm_to_3dprint.cli bambu-capture-template examples/bambu_a1_hybrid_project.json /path/to/studio_saved.3mf --output generated/output/a1_seed_template.3mf
```

If you want to expose the same workflow as a local MCP server for Codex or another MCP client,
run the built-in stdio server:

```bash
python3 -m llm_to_3dprint.cli bambu-mcp-server
```

The MCP server keeps the surface intentionally small:

- `probe_bambu_studio`
- `setup_bambu_hammerspoon`
- `validate_bambu_project`
- `render_bambu_handoff`
- `build_bambu_cli_assemble_list`
- `export_bambu_3mf_cli`
- `export_bambu_3mf_gui`
- `patch_bambu_studio_3mf`
- `apply_bambu_seed_template`
- `check_bambu_seed_template`
- `capture_bambu_seed_template`

## Project Layout

- `docs/generalised-specification.md`: cleaned version of the workflow specification.
- `docs/bambu_3mf_pipeline.md`: architecture and constraints for Bambu Studio-backed `.3mf` workflows.
- `examples/rectangular_enclosure.json`: sample structured brief.
- `examples/friction_lid_enclosure.json`: sample brief with explicit closure metadata.
- `examples/bambu_a1_hybrid_project.json`: sample Bambu Studio handoff spec for an A1 + AMS lite.
- `src/llm_to_3dprint/bambu.py`: Bambu handoff schema, validation, presets, patch helpers, and handoff plan builder.
- `src/llm_to_3dprint/bambu_mcp.py`: thin stdio MCP entry module and test helpers.
- `src/llm_to_3dprint/bambu_mcp_server.py`: MCP tool definitions, request handling, and stdio server loop.
- `src/llm_to_3dprint/brief.py`: schema, validation, presets, JSON IO.
- `src/llm_to_3dprint/prompting.py`: prompt builder for LLM-assisted code generation.
- `src/llm_to_3dprint/renderers.py`: starter CadQuery renderer.
- `src/llm_to_3dprint/cli.py`: command-line interface.
- `tests/`: lightweight tests for validation, prompt generation, and script rendering.

## Brief Format

The design brief uses these coordinate conventions:

- Units are millimeters unless noted otherwise.
- `x`: left/right offset from the model center.
- `y`: front/back offset from the model center.
- `z`: height from the bottom face.
- Cutouts are face-aligned features whose center is described with those coordinates.

For example, a front-face cutout uses:

- `face="front"`
- `x` for side-to-side placement
- `z` for height from the bottom

Optional closure metadata can describe how a lid is intended to seat and print:

- `closure.type`: closure strategy such as `friction_lid`
- `closure.insert_depth`: how far the mating lip or insert feature extends into the base
- `closure.seat_z`: explicit seated Z position for the lid, if known
- `closure.target_clearance`: intended fit clearance
- `closure.assembled_orientation`: how the lid should face when closed
- `closure.print_orientation`: how the lid should be exported for printing
- `closure.supports_allowed`: whether the chosen print orientation may require supports
- `closure.decorate_exterior_only`: whether restyling should avoid the mating interface

For multi-part enclosures, keep print orientation and assembled orientation explicit.
A lid that previews correctly can still be mechanically wrong if the mating lip is built
on the same side as the exterior styling. Validate the seated assembly, not just the
isolated solids.

For Bambu targets, treat `.3mf` as a project/profile format, not just a neutral mesh container.
The reliable workflow is:

1. Generate CAD geometry.
2. Describe the intended part grouping and filament mapping with a Bambu handoff spec.
3. Use Bambu Studio, or a tool that drives Bambu Studio, to save the final printer-facing `.3mf`.

The Studio-backed CLI path is also usable directly from this repo:

- `bambu-probe`: detect the install and show preset resolution
- `bambu-setup-hammerspoon`: install the minimal `hs.ipc` bootstrap block and verify Hammerspoon IPC
- `bambu-build-cli`: emit the Bambu assemble-list JSON
- `bambu-export-cli`: attempt the Studio CLI export and report the result
- `bambu-export-gui`: drive the Studio GUI and save the in-place multicolor `.3mf`, preferring `seed_template_3mf` when configured
- `bambu-patch-3mf`: patch a Studio-authored `.3mf` back into the validated multicolor layout
- `bambu-apply-template`: populate a fresh output from a known-good seed Studio `.3mf`
- `bambu-check-template`: verify that a Studio-authored seed `.3mf` matches the spec’s patchable objects
- `bambu-capture-template`: validate and copy a Studio-authored seed `.3mf` into the project template path
- `bambu-mcp-server`: expose the same validated workflow as stdio MCP tools

The same operations are exposed by the local MCP server so a Codex agent can keep the whole
workflow tool-driven instead of shell-driven.

`seed_template_3mf` is optional on a `BambuProjectSpec`, but recommended for stable automation.
It should point to a known-good Studio-authored `.3mf` that already matches the intended printer,
plate structure, and part tree. The repo’s template-backed path then patches that seed into a
fresh output rather than rebuilding the entire project state from scratch.

Grouped multipart CLI imports must use STL/OBJ meshes. If the CAD source is STEP, the driver resolves a sibling `.stl` or `.obj` file for the Studio CLI path.

Current Bambu Studio CLI notes from real runtime testing on this Mac:

- The CLI `assemble_list` path accepts mesh inputs for assembly (`.stl` and `.obj`), not `STEP`.
- If a grouped handoff part is authored as `STEP`, the driver looks for a same-stem `.stl` sibling.
- The installed `BambuStudio 02.05.00.66` build exposes `--export-3mf`, but currently crashes on this host during export even after loading valid A1 machine/process/filament presets.
- GUI export is validated for the grouped multicolor lid workflow on this Mac, but it needs macOS assistive-access permission for the calling process. The merge click now supports `auto`, `swift`, and `hammerspoon` backends, with `auto` preferring Hammerspoon when it is installed and ready.
- The GUI exporter does not yet serialize the full hybrid project with side-by-side accents and the separate base in one pass.

## Why This Shape

This scaffold is meant to operationalize the workflow before over-engineering it:

- The brief keeps the LLM input explicit.
- The validator catches common bad dimensions early.
- The prompt builder gives you a repeatable LLM instruction block.
- The renderer gives you a real Python CAD starting point instead of only prose.

## Next Extensions

- Add renderers for cylindrical enclosures, trays, brackets, and decorative solids.
- Add OpenAI or other LLM API integration on top of the prompt builder.
- Add geometry checks once CAD dependencies are installed in CI.
- Extend the MCP/GUI exporter from the grouped multicolor lid path to full hybrid projects with separate base and accent objects.
