# Multicolor Backends

Read this file when the user wants multicolor output, a slicer-native project, a printer-specific multi-part layout, or "one click" printer-ready results.

## First Decision

Resolve the real deliverable before modeling:

- `geometry only`: aligned `STL`/`STEP` bodies or parts
- `slicer handoff`: geometry plus a machine-readable grouping and filament spec
- `printer-native project`: a slicer-authored or validated `3MF`/project file
- `plate-ready 3MF set`: one standard `3MF` per build plate when a printer-native serializer is unavailable

Do not describe plain `STL` as a reliable multicolor artifact.

## Strategy Selector

Choose the color approach before adding detail:

- `in-place multicolor`
  Use when the backend is proven to preserve same-part color bodies.
  Best for badges, stripes, raised islands, and simple top-face accents.
- `separate inserts`
  Use when fit matters and the backend is fragile.
  Best for flush logos, labels, bezels, and small accent plates.
- `side-by-side accent parts`
  Use when the accent does not need to be fused into the main body.
  Best for appliques, vent caps, knobs, or decorative panels.
- `hybrid`
  Use when some details should print in-place and others should remain separate.
  This is often the best path for consumer AMS/MMU printers.

## Design Rules

- Prefer slightly proud or debossed color regions over perfectly flush coplanar regions unless the slicer path is already proven.
- Keep in-place color bodies as distinct non-overlapping solids with clean adjacency.
- Preserve the internal fit first. Apply styling and color breakup second.
- For enclosure lids, validate the final seated orientation after any color-body changes.
- If a user wants low-waste multicolor printing, reduce tiny scattered islands and keep color regions contiguous.

## Generic Handoff

When no slicer-specific backend is required:

- export one aligned solid per color region or per physical part
- keep filenames explicit, for example:
  - `lid_shell.stl`
  - `lid_inserts.stl`
  - `lid_accent.stl`
- export `STEP` when the receiving tool benefits from preserved solid structure
- include a short handoff note that states:
  - which parts are meant to be one object with multiple colors
  - which parts stay separate
  - which filament each part should use
  - which build plate each object should use when the model is too large for one bed

For single-color multi-part prints, standard `3MF` can still be useful as a plate-level geometry package. Prefer one `3MF` per plate over one oversized all-parts bundle when the complete design does not fit on the printer bed.

## Bambu Studio

For Bambu-style "one click" output, raw geometry is only the handoff layer. The final artifact should be a Bambu-native project.

Use this order:

1. model aligned color bodies or parts
2. define grouping, plate, and filament intent
3. use Bambu Studio as the final serializer
4. if available, prefer a validated handoff spec plus seed-template workflow over ad hoc imports

Practical rules:

- `STEP`/`STL` imports are not enough by themselves for a Handy-style result
- grouped imports can be structurally different from the final visible multicolor project
- if the repo already has Bambu tooling, use it instead of inventing a custom exporter
- if a valid seed template exists, prefer patching from that template for repeatable output
- for single-color parts that are split because of bed size, still create the Bambu handoff spec and attempt a Studio-authored `3MF`; if Studio export is not available, provide plate-ready standard `3MF` files as the fallback
- single-material fallback `3MF` files should use neutral direct-mesh structure unless a known-good Studio template is being patched: put mesh objects directly in `3D/3dmodel.model` resources and point build items directly at those objects
- Bambu-style component wrappers and `3D/Objects/object_N.model` are appropriate for Studio-authored templates, but partial clean-room use of that structure can be rejected as having no geometry
- validate Bambu-readable geometry with `BambuStudio --info file.3mf` when the CLI exists; a passing result should report dimensions, facet count, manifold status, and volume
- if a Bambu-resaved project ZIP-tests correctly but `--info` does not report geometry, do not prefer it over a neutral direct-mesh fallback that does report geometry
- after validation, leave only the recommended user-facing files in the output folder or move diagnostics out of the way

If working in the `LLM_to_3DPrint` repo, read `docs/bambu_3mf_pipeline.md` before promising a final Bambu `3MF`.

## PrusaSlicer / OrcaSlicer

Use the same design strategy rules, but do not assume Bambu-specific project behavior.

Default safe path:

- export separate aligned solids
- import them into the target slicer as parts or objects
- assign extruders there
- save the slicer-native project only after checking that the visible object tree matches the intended grouping

If the user only needs printable geometry, stop at aligned `STL`/`STEP` plus clear filenames.

## Verification Checklist

For multicolor requests, verify the right layer:

- geometry builds successfully
- mating parts still seat without interference
- color bodies do not overlap unless intentionally unioned
- in-place color bodies remain aligned in the final print orientation
- separate inserts still fit after styling changes
- backend export succeeds
- final project maps each intended part or body to the expected filament
- final project structure matches the target slicer expectations, not just the metadata
- target slicer import/info tooling reports real geometry, not merely a successful archive read

If a supposedly successful export does not look multicolor in the slicer, inspect the project structure directly instead of trusting the export status line.

## Failure Rules

- If the backend is unproven, say so and fall back to aligned geometry plus a handoff spec.
- If a printer-native result depends on a slicer-specific format, do not claim completion until that project opens correctly in the target slicer.
- If the user wants a reusable production workflow, prefer deterministic scripts and validated templates over manual click sequences.
