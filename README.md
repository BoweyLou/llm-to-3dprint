# LLM to 3D Print

`llm-to-3dprint` is a structured workflow for turning natural-language part requirements into:

- validated JSON design briefs
- repeatable LLM prompts for Python CAD generation
- starter CadQuery scripts for enclosure-style parts
- enclosure fit checks
- experimental Bambu Studio `.3mf` handoff and automation

The repo is intentionally opinionated. It is strongest today for rectangular enclosure workflows and Bambu A1 multicolor handoff experiments, not arbitrary CAD generation.

## Status

### Stable Enough For Review

- Structured brief schema and validation
- Prompt generation for LLM-assisted CAD workflows
- Starter CadQuery renderer for rectangular and cavity-style parts
- Enclosure fit validation for seated lids
- Bambu handoff spec generation and validation
- Seed-template patching for Bambu Studio-authored multicolor `.3mf` projects

### Experimental

- Direct Bambu Studio CLI `.3mf` export
- GUI automation via macOS accessibility and Hammerspoon
- Full hybrid Bambu project packaging in one saved `.3mf`
- Geometry generation outside enclosure-style part families

## Private Review Scope

This repo is currently meant to review four things:

1. Whether the brief -> prompt -> CAD-script workflow is usable.
2. Whether enclosure fit checking is a meaningful guardrail.
3. Whether Bambu handoff specs are the right abstraction for multicolor output.
4. Whether the current Bambu Studio automation approach is worth hardening.

It is not yet positioned as a polished end-user product, a general-purpose CAD engine, or a cross-platform slicer automation layer.

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

### Bambu Workflow

Create a starter Bambu handoff spec:

```bash
python3 -m llm_to_3dprint.cli init-bambu-project --output examples/bambu_a1_hybrid_project.json
```

Validate it:

```bash
python3 -m llm_to_3dprint.cli validate-bambu-project examples/bambu_a1_hybrid_project.json
```

Render a human-readable handoff:

```bash
python3 -m llm_to_3dprint.cli bambu-handoff examples/bambu_a1_hybrid_project.json --output generated/bambu_handoff.md
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

## Project Layout

- `docs/generalised-specification.md`: generalized workflow specification
- `docs/bambu_3mf_pipeline.md`: Bambu architecture, limits, and current automation shape
- `docs/public-release-checklist.md`: first pass of public-release work items
- `docs/privacy-sweep.md`: current privacy review and findings
- `examples/rectangular_enclosure.json`: starter brief
- `examples/friction_lid_enclosure.json`: enclosure brief with explicit closure metadata
- `examples/bambu_a1_hybrid_project.json`: A1 + AMS lite multicolor handoff spec
- `src/llm_to_3dprint/brief.py`: brief schema, validation, presets, and JSON IO
- `src/llm_to_3dprint/prompting.py`: prompt builder for LLM-assisted CAD generation
- `src/llm_to_3dprint/renderers.py`: starter CadQuery renderer
- `src/llm_to_3dprint/fitcheck.py`: enclosure fit-check logic
- `src/llm_to_3dprint/bambu.py`: Bambu handoff schema, validation, patch helpers, and export orchestration
- `src/llm_to_3dprint/bambu_mcp_server.py`: local MCP server over the Bambu workflow
- `tests/`: focused tests for schemas, fit checks, renderers, and Bambu paths
- `generated/`: reviewable example inputs, scripts, and output artifacts

## Design Notes

- Units are millimeters unless stated otherwise.
- Briefs keep print orientation and assembled orientation explicit when lids are involved.
- For Bambu targets, `.3mf` is treated as a printer project/profile, not just a mesh container.
- The current multicolor recommendation is backend-aware: avoid assuming raw `STEP` or `STL` alone is enough for a printer-ready result.

## Review Notes

- The current Bambu flow is validated primarily around an A1 + AMS lite multicolor lid example.
- Host-specific runtime caveats and serializer details live in [docs/bambu_3mf_pipeline.md](docs/bambu_3mf_pipeline.md).
- Public-release cleanup items live in [docs/public-release-checklist.md](docs/public-release-checklist.md).
