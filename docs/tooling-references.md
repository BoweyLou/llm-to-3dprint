# Tooling References

This repo references official docs instead of copying upstream documentation. Keep this file compact: pin the supported target range, link to the source of truth, and capture only local gotchas that affect this workflow.

## Target Toolchain

| Tool | Target range | Role | Source of truth |
| --- | --- | --- | --- |
| CadQuery | `2.7.x` | Primary BREP CAD backend for precise mechanical parts and current starter renderer output. | <https://cadquery.readthedocs.io/> |
| build123d | `0.10.x` | Alternative BREP CAD backend for Pythonic/topology-heavy modeling work. | <https://build123d.readthedocs.io/> |
| CAD Skills / text-to-cad | Reviewed commit `ea4f38b` | Preferred external generation, STEP inspection, CAD Explorer review, and `@cad[...]` reference workflow for clean build123d parts when the skill is installed. | <https://github.com/earthtojake/text-to-cad> |
| Blender | `4.5 LTS` for conservative review, `5.1.x` exploratory | Optional visual review, canonical screenshots, scene inspection, and aesthetic refinement. | <https://docs.blender.org/api/> |
| Bambu Studio | Host-verified current install | Authoritative serializer for Bambu printer-facing `3MF` projects. | <https://github.com/bambulab/BambuStudio> |
| Model Context Protocol | `2025-06-18` server today; evaluate `2025-11-25` next | Local tool interface for Bambu automation and future Blender/review resources. | <https://modelcontextprotocol.io/specification> |

## Local Rules

- Prefer CadQuery/build123d as the source of truth for functional printed geometry.
- When CAD Skills / text-to-cad is installed, prefer its build123d + STEP-first workflow for new clean mechanical parts, then feed validated STEP/STL/3MF artifacts into this repo's Bambu or print-handoff layer when needed.
- Configure CAD Skills with `TEXT_TO_CAD_SKILL_DIR`; use `cad-skills-probe` and `cad-skills-pilot` instead of importing or vendoring the upstream toolchain.
- Use Blender as review tooling unless the part is intentionally decorative, organic, or scene-like.
- Treat generated screenshots and Blender measurements as feedback into the CAD loop, not as replacements for parametric constraints.
- Treat CAD Explorer as the first visual review layer for clean STEP/STL/3MF outputs; keep Blender for scene-level inspection, aesthetic review, or workflows CAD Explorer cannot cover.
- Use `validate-artifacts` before Bambu export to catch missing artifacts, empty meshes, obvious bed-fit failures, and unavailable geometry metrics.
- Do not ingest full upstream docs into this repo. Add small geometry recipes and local gotchas instead.
- Update this file when `pyproject.toml`, MCP protocol support, or the preferred Blender review target changes.

## Current Compatibility Notes

- The `cad` extra pins CadQuery and build123d to the current minor release families to avoid silent API drift.
- CadQuery and build123d are both OpenCascade-backed BREP workflows, so they are preferred for dimensions, clearances, shells, lids, ramps, and connectors.
- CAD Skills is a skill/tool bundle rather than a pinned Python library. Do not vendor it into this repo until a pilot proves the wrapper contract is stable.
- Blender review work should import exported `STL` or `OBJ` artifacts directly, document STEP/3MF import limitations, render canonical views, and report measured facts back into the design loop.
- Bambu `3MF` output remains backend-specific; Studio-authored templates and Bambu Studio serialization remain the production path for printer-native projects.
