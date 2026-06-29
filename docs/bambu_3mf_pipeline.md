# Bambu 3MF Pipeline

This repo now treats Bambu output as a two-stage workflow:

1. Generate geometry and an explicit Bambu handoff spec.
2. Use Bambu Studio as the authoritative serializer for the final `.3mf` print profile.

That decision is deliberate. MakerWorld and Bambu Handy "one click" prints are not just meshes.
They are Bambu Studio projects with printer settings, object grouping, plate placement, and
filament assignments already embedded.

## What The Research Changed

The recent investigation showed three practical constraints:

1. Raw `STEP` and `STL` imports are only geometry handoff.
2. Bambu Studio uses a Bambu-specific 3MF layer with extra metadata files beyond neutral 3MF.
3. Flush multicolor details are fragile if the workflow depends on Studio reconstructing the
   intended part tree from geometry alone.

Based on Bambu Studio source review, the final profile serializer writes extra members such as:

- `Metadata/print_profile.config`
- `Metadata/project_settings.config`
- `Metadata/model_settings.config`
- `Metadata/slice_info.config`
- `Metadata/filament_sequence.json`

Those details live in Bambu Studio's `bbs_3mf` export path. That makes a clean-room writer
possible, but it is the wrong first implementation because it would be version-fragile from day one.

## Recommended Backend Order

1. `bambu_studio_gui`
   Use Bambu Studio directly, or drive it through an MCP/tool wrapper.
2. `bambu_studio_cli`
   Use this only on hosts where `--export-3mf` has been verified to work reliably.
3. `clean_room_3mf`
   Use only if Studio-backed automation is impossible and you accept a much higher maintenance cost.

## Repo Support

The new `llm_to_3dprint.bambu` module adds:

- `BambuProjectSpec`: target printer, AMS mode, filament count, output `.3mf`, and part list
- `BambuPartSpec`: per-file import strategy, part grouping, plate assignment, and filament mapping
- `build_bambu_handoff(...)`: a stable import/save plan for Codex and the local MCP wrapper
- `build_cli_assemble_payload(...)`: the exact `assemble_list.json` shape used by Bambu Studio CLI
- `export_3mf_with_bambu_cli(...)`: a real CLI export attempt that reports output existence and crash context
- `export_3mf_with_bambu_gui(...)`: a GUI-backed export path that imports the grouped in-place multicolor object, accepts the multipart merge dialog, and saves a Studio-authored `.3mf`; when `seed_template_3mf` is configured, it now prefers the seed-template path up front so the retro lid case keeps the separate-object multicolor structure
- `patch_studio_3mf_multicolor(...)`: rewrite a Studio-authored `.3mf` so the validated object/filament mapping survives the round-trip
- `apply_seed_template_3mf(...)`: patch a known-good Studio seed template into a fresh output using the Bambu project spec
- `check_seed_template_3mf(...)`: verify that a Studio-authored seed template contains the expected patchable objects
- `capture_seed_template_3mf(...)`: validate and copy a Studio-authored template into the repo-managed seed-template path
- `llm_to_3dprint.bambu_mcp`: a thin stdio MCP server over the stable probe/validate/export/patch operations
- `setup_hammerspoon_for_bambu(...)`: bootstrap `hs.ipc`, restart Hammerspoon, and verify the repo-managed action bundle can be used

The CLI now exposes:

- `init-bambu-project`
- `validate-bambu-project`
- `validate-artifacts`
- `bambu-handoff`
- `blender-review`
- `bambu-probe`
- `bambu-setup-hammerspoon`
- `bambu-build-cli`
- `bambu-export-cli`
- `bambu-export-gui`
- `bambu-patch-3mf`
- `bambu-apply-template`
- `bambu-check-template`
- `bambu-capture-template`
- `bambu-mcp-server`

The MCP server exposes the same stable workflow as tools:

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

It also exposes local resources and prompts for the surrounding agent workflow:

- resources for the backlog, geometry recipes, starter brief, and Bambu handoff example
- prompts for reviewing a generated part, preparing a Bambu handoff, and validating a design contract

## Current Runtime Limits

The Studio CLI path is not hypothetical anymore, but it has hard current limits:

- multipart CLI assembly uses mesh inputs for assembly, not `STEP`
- the driver therefore resolves grouped parts to `.stl` or `.obj`
- in current local macOS validation, `BambuStudio 02.05.00.66` still crashes during `--export-3mf`, even after loading valid A1 presets
- GUI export is validated for the grouped in-place multicolor object on a macOS host with accessibility access enabled. When a valid `seed_template_3mf` is configured, the exporter now skips the grouped import flow and patches directly from that seed template. The merge-confirmation step now supports `auto`, `swift`, and `hammerspoon` click backends, with `auto` preferring Hammerspoon when it is installed and its CLI is ready
- the GUI exporter does not yet serialize the full hybrid project with separate accent/base objects in one pass
- the new patch command is the most reliable way to repair a Studio-authored `.3mf` that already exists on disk
- the patch command currently targets single-nozzle Studio projects where object names or source filenames match the Bambu handoff spec

That means the repo can now prepare the exact CLI inputs and attempt export honestly, but it does not
pretend the `.3mf` was created when Studio crashes before writing it.

## Why This Helps Codex

An AI agent cannot reliably jump from CAD geometry to a Bambu-ready print profile without an
explicit part grouping contract. The new spec makes the missing state visible:

- which files should merge into one multipart object
- which parts should stay side-by-side
- which filament each part should use
- which backend should produce the final `.3mf`

That is enough to support two real paths:

1. A Codex workflow that prepares geometry plus a Bambu handoff spec and then drives Studio through tools.
2. The local MCP server that ingests `BambuProjectSpec`, automates Studio, and saves or patches the final `.3mf`.

## MCP Direction

The current implementation keeps the MCP surface thin and file-driven on purpose:

- load a validated `BambuProjectSpec` from disk
- call the stable export or patch path
- expose repo-owned reference resources and prompt scaffolds without mutating files
- return structured results directly from the underlying dataclasses

The recommended production path is now template-backed:

1. Save a known-good Studio-authored seed `.3mf` for the target printer/profile.
2. Store that path as `seed_template_3mf` on the `BambuProjectSpec`.
3. Use `bambu-check-template` or `check_bambu_seed_template` to confirm the seed still matches the expected in-place multicolor objects.
4. Use `bambu-capture-template` or `capture_bambu_seed_template` when a new Studio-authored template should replace the stored seed.
5. Use `bambu-apply-template` or `apply_bambu_seed_template` to patch a fresh output from that seed.

That keeps Bambu Studio as the authority for printer-facing project structure while moving the
repeatable, programmable part of the workflow into Codex-owned code.

That is the right level for now. It lets Codex run the end-to-end workflow through tools
without freezing the server API around Bambu Studio UI details that are still host-specific.
