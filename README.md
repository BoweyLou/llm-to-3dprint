# LLM to 3D Print

`llm-to-3dprint` is a structured workflow for turning natural-language part requirements into:

- validated JSON design briefs
- repeatable LLM prompts for Python CAD generation
- starter CadQuery scripts for enclosure-style parts
- enclosure fit checks
- mesh-preserved drawer conversion for one-piece artistic 3MF models
- experimental Bambu Studio `.3mf` handoff and automation

The repo is intentionally opinionated. It is strongest today for rectangular enclosure workflows and Bambu A1 multicolor handoff experiments, not arbitrary CAD generation.

## Status

### Stable Enough For Review

- Structured brief schema and validation
- Prompt generation for LLM-assisted CAD workflows
- Starter CadQuery renderer for rectangular and cavity-style parts
- Enclosure fit validation for seated lids
- Mesh-preserved drawer partitioning for one-piece 3MF models where source surface triangles must be retained
- Bambu handoff spec generation and validation
- Seed-template patching for Bambu Studio-authored multicolor `.3mf` projects

### Experimental

- Direct Bambu Studio CLI `.3mf` export
- GUI automation via macOS accessibility and Hammerspoon
- Full hybrid Bambu project packaging in one saved `.3mf`
- Geometry generation outside enclosure-style part families

## Current Scope

This public repo is currently focused on four things:

1. A structured brief -> prompt -> CAD-script workflow for enclosure-style parts.
2. Mechanical fit validation for seated lids.
3. A backend-aware multicolor handoff model for Bambu workflows.
4. Local tooling and MCP support for driving that workflow end to end.
5. Mesh-first repair workflows for preserving artistic source meshes while adding functional generated geometry.

It is not positioned as a general-purpose CAD engine, a polished consumer app, or a cross-platform slicer automation layer.

## Quick Start

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

If you want to execute generated CAD scripts locally, also install:

```bash
pip install -e ".[cad]"
```

### Core CAD Workflow

Create a starter brief:

```bash
python3 -m llm_to_3dprint.cli init-brief --output examples/rectangular_enclosure.json
```

Validate the brief:

```bash
python3 -m llm_to_3dprint.cli validate examples/rectangular_enclosure.json
```

Validate the design-intent contract before generating CAD:

```bash
python3 -m llm_to_3dprint.cli validate-design examples/rectangular_enclosure.json
```

Generate an LLM prompt:

```bash
python3 -m llm_to_3dprint.cli prompt examples/rectangular_enclosure.json --output generated/enclosure_prompt.md
```

Render a starter CadQuery script:

```bash
python3 -m llm_to_3dprint.cli render examples/rectangular_enclosure.json --output generated/enclosure.py
```

If `cadquery` is installed, run the generated script to export STL and STEP files into `generated/output/`.

For enclosure-style scripts that expose `build_base()` and `build_lid()`, check seated fit with:

```bash
python3 -m llm_to_3dprint.cli check-fit generated/my_enclosure.py
```

The fit checker resolves seat height from one of:

- `get_lid_seat_height()`
- `LID_SEAT_Z`
- `BASE_OUTER_HEIGHT` and `LID_LIP_DEPTH`

### Mesh-Preserved Drawer Workflow

Use this path when a source 3MF must remain the visible surface of the final print. The workflow partitions original source triangles across fixed and moving parts, selecting drawer skins from the front-visible surface inside each coarse drawer mask, then adds generated backing, cavity, and tray geometry behind the preserved skin.

```bash
PYTHONPATH=src python3 -m llm_to_3dprint.cli validate-design generated/desk_organiser_mesh_preserved_brief.json
PYTHONPATH=src python3 -m llm_to_3dprint.cli build-mesh-drawers generated/desk_organiser_mesh_preserved_brief.json --output-dir generated/output/desk_organiser_mesh_preserved_drawers
PYTHONPATH=src python3 -m llm_to_3dprint.cli validate-mesh-manifest generated/output/desk_organiser_mesh_preserved_drawers/desk_organiser_mesh_preserved_drawers_mesh_manifest.json
```

The manifest is the audit trail: every source triangle must appear exactly once across the body and drawer outputs. STL/3MF are the authoritative outputs for this workflow because STEP does not preserve the original triangle mesh skin.

For v3 mesh-preserved drawer work, install the mesh extra when you want the researched raycast/boolean stack available:

```bash
python3 -m pip install -e ".[mesh]"
```

`build-mesh-drawers` writes five 3MF files: a mesh-preserved print 3MF that contains the original source skins plus generated shell/backing/functional geometry arranged for printing, an assembled preview 3MF that keeps the same mesh-preserved objects in assembled position for visual checking, a front-review 3MF rotated for Bambu's camera to show the drawer side, a source-skin preview 3MF that contains only the original source triangles split across body/drawer patches, and a functional-core diagnostic 3MF that contains only the generated drawer/body solids. `validate-mesh-manifest` checks source-triangle accounting, functional drawer clearance, and slicer-closed geometry health for the mesh-preserved print output. It also records stricter multi-shell edge topology separately so Bambu-ready closure is not confused with a mathematically single-shell CAD solid. Drawer-front masks use a front-normal gate so recessed side facets stay on the fixed body, and removable drawer skins now use flat backing caps instead of a duplicate sculpted inner skin so decorative relief boundaries do not become fin-like shell artifacts.

### Bambu Workflow

Create a starter Bambu handoff spec:

```bash
python3 -m llm_to_3dprint.cli init-bambu-project --output examples/bambu_a1_hybrid_project.json
```

Validate it:

```bash
python3 -m llm_to_3dprint.cli validate-bambu-project examples/bambu_a1_hybrid_project.json
```

Validate referenced geometry artifacts before export:

```bash
python3 -m llm_to_3dprint.cli validate-artifacts examples/bambu_a1_hybrid_project.json
```

Render a human-readable handoff:

```bash
python3 -m llm_to_3dprint.cli bambu-handoff examples/bambu_a1_hybrid_project.json --output generated/bambu_handoff.md
```

Write an optional Blender review plan and canonical render script:

```bash
python3 -m llm_to_3dprint.cli blender-review examples/bambu_a1_hybrid_project.json --output-dir generated/reviews/a1_handoff
```

Probe the local Bambu Studio runtime:

```bash
python3 -m llm_to_3dprint.cli bambu-probe
```

The most reliable current multicolor path is template-backed:

```bash
python3 -m llm_to_3dprint.cli bambu-check-template examples/bambu_a1_hybrid_project.json
python3 -m llm_to_3dprint.cli bambu-apply-template examples/bambu_a1_hybrid_project.json --output generated/output/out.3mf
```

If you need GUI-driven export:

```bash
python3 -m llm_to_3dprint.cli bambu-setup-hammerspoon
python3 -m llm_to_3dprint.cli bambu-export-gui examples/bambu_a1_hybrid_project.json --output generated/output/out.3mf --click-backend auto
```

Use the direct Studio CLI path only as an experiment:

```bash
python3 -m llm_to_3dprint.cli bambu-build-cli examples/bambu_a1_hybrid_project.json --output generated/bambu_assemble_list.json
python3 -m llm_to_3dprint.cli bambu-export-cli examples/bambu_a1_hybrid_project.json --assemble-output generated/bambu_assemble_list.json
```

### CAD Skills Adapter

For clean mechanical CAD work, this repo can route an explicit pilot through an external CAD Skills / text-to-cad checkout without vendoring that toolchain:

```bash
TEXT_TO_CAD_SKILL_DIR=/path/to/text-to-cad python3 -m llm_to_3dprint.cli cad-skills-probe
TEXT_TO_CAD_SKILL_DIR=/path/to/text-to-cad python3 -m llm_to_3dprint.cli cad-skills-pilot --generator generated/my_part.py --output-dir generated/output/my_part_cad_skills
```

The pilot is a dry run unless `--run` is passed. When the external checkout is unavailable, keep using this repo's brief, validation, local renderer, mesh-preserved, and Bambu handoff paths.

## Documentation Contract

This repo uses `doc-contract-kit` guardrails so code, workflow, and docs changes stay aligned.

Run the local docs contract check with:

```bash
make docs-check
```

The repo-specific rules live in `doc-contract.json`. Current planning items are tracked in
[docs/backlog.md](docs/backlog.md).

## Local MCP Server

If you want Codex or another MCP client to drive the Bambu workflow through tools instead of shell commands:

```bash
python3 -m llm_to_3dprint.cli bambu-mcp-server
```

Current MCP tools:

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

Current MCP resources:

- `llm-to-3dprint://docs/backlog`
- `llm-to-3dprint://docs/geometry-recipes`
- `llm-to-3dprint://examples/rectangular-brief`
- `llm-to-3dprint://examples/bambu-a1-handoff`

Current MCP prompts:

- `review_generated_part`
- `prepare_bambu_handoff`
- `validate_design_contract`

## Project Layout

- `docs/generalised-specification.md`: generalized workflow specification
- `docs/bambu_3mf_pipeline.md`: Bambu architecture, limits, and current automation shape
- `docs/tooling-references.md`: pinned toolchain references and local CAD/Blender gotchas
- `docs/geometry-recipes.md`: repo-owned modeling recipes and shape-contract expectations
- `docs/backlog.md`: active backlog for CAD, Blender review, MCP, and governance work
- `docs/public-release-checklist.md`: first pass of public-release work items
- `docs/privacy-sweep.md`: current privacy review and findings
- `examples/rectangular_enclosure.json`: starter brief
- `examples/friction_lid_enclosure.json`: enclosure brief with explicit closure metadata
- `examples/bambu_a1_hybrid_project.json`: A1 + AMS lite multicolor handoff spec
- `src/llm_to_3dprint/brief.py`: brief schema, validation, presets, and JSON IO
- `src/llm_to_3dprint/prompting.py`: prompt builder for LLM-assisted CAD generation
- `src/llm_to_3dprint/renderers.py`: starter CadQuery renderer
- `src/llm_to_3dprint/mesh_drawers.py`: mesh-preserved drawer partitioning and STL/3MF export
- `src/llm_to_3dprint/fitcheck.py`: enclosure fit-check logic
- `src/llm_to_3dprint/artifact_validation.py`: pre-export artifact, bounds, and bed-fit checks
- `src/llm_to_3dprint/blender_review.py`: optional Blender review plan and render-script generation
- `src/llm_to_3dprint/cad_skills.py`: thin external CAD Skills / text-to-cad adapter
- `src/llm_to_3dprint/bambu.py`: Bambu handoff schema, validation, patch helpers, and export orchestration
- `src/llm_to_3dprint/bambu_mcp_server.py`: local MCP server over the Bambu workflow
- `tests/`: focused tests for schemas, fit checks, renderers, and Bambu paths
- `generated/`: a small demo set of generated scripts and representative output artifacts

## Design Notes

- Units are millimeters unless stated otherwise.
- Briefs keep print orientation and assembled orientation explicit when lids are involved.
- For Bambu targets, `.3mf` is treated as a printer project/profile, not just a mesh container.
- The current multicolor recommendation is backend-aware: avoid assuming raw `STEP` or `STL` alone is enough for a printer-ready result.

## Review Notes

- The current Bambu flow is validated primarily around an A1 + AMS lite multicolor lid example.
- Host-specific runtime caveats and serializer details live in [docs/bambu_3mf_pipeline.md](docs/bambu_3mf_pipeline.md).
- Public-release cleanup items live in [docs/public-release-checklist.md](docs/public-release-checklist.md).
