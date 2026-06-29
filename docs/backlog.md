# Backlog

This backlog captures the CAD, Blender, MCP, and documentation-governance work identified on 2026-04-23. Keep it scoped to durable product and workflow improvements rather than one-off generated artifacts.

## Machine-Readable Status Mirror

- [x] CAD-001 Add a design-spec layer before code generation.
- [x] CAD-002 Generate shape contracts before full geometry.
- [x] CAD-003 Add automated geometry checks before export.
- [x] CAD-004 Add Blender preview and screenshot review.
- [x] CAD-005 Define Blender's role for aesthetic refinement.
- [x] CAD-006 Preserve CadQuery/build123d as the mechanical spine.
- [x] CAD-007 Rebuild mesh-preserved drawers as skin plus functional solids.
- [x] CAD-008 Route clean CAD generation through CAD Skills / text-to-cad when available.
- [x] GOV-001 Pin target tool versions.
- [x] GOV-002 Create repo-owned geometry recipes.
- [x] GOV-003 Extend design contracts in briefs.
- [x] GOV-004 Add validation before export.
- [x] GOV-005 Use Blender as review tooling.
- [x] GOV-006 Keep compact external documentation references.
- [x] GOV-007 Add a thin CAD Skills adapter and pilot workflow.
- [x] MCP-001 Add MCP resources for repo-local design and handoff references.
- [x] MCP-002 Add MCP prompts for review, Bambu handoff, and design-contract workflows.
- [>] MCP-003 Consider durable task handling for long-running Bambu and Blender operations after the local server targets a newer MCP protocol revision.

## CAD And Blender Improvement Backlog

1. Add a design-spec layer before code generation.
   - Status: Done
   - Why: Natural-language requirements need explicit silhouette, style, smoothness, symmetry, slope, wall, and forbidden-shape constraints before CAD code is written.
   - Done when: Non-trivial briefs can express visual/form constraints separately from dimensions and manufacturing constraints.
   - Progress: Added initial `design_intent` brief metadata for silhouette, visual style, symmetry, surface continuity, smoothness, slope, wall, forbidden-feature, and cross-section constraints.

2. Generate shape contracts before full geometry.
   - Status: Done
   - Why: Weird shapes are easier to catch at top-profile, side-profile, cross-section, seam, and contact-surface checkpoints than after a full model is exported.
   - Done when: CAD generation can produce and validate intermediate profiles for ramps, enclosures, lids, seams, and connectors.
   - Progress: Added initial geometry recipes that define brief-level shape-contract expectations for ramps, shells, lids, seams, and plate splits.

3. Add automated geometry checks before export.
   - Status: Done
   - Why: The workflow needs hard checks for dimensions, slope, overhang risk, wall assumptions, bed fit, segment alignment, clearances, contact, and obvious mesh anomalies.
   - Done when: Generated outputs include a structured verification report before STL, STEP, or 3MF handoff.
   - Progress: Added `validate-artifacts` plus `artifact_validation.py` to check Bambu handoff artifact existence, mesh bounds for STL/OBJ/3MF, empty meshes, and known Bambu bed-fit failures before export. STEP bounds remain delegated to CAD Skills/CAD-kernel inspection.

4. Add Blender preview and screenshot review.
   - Status: Done
   - Why: Blender is better used as a visual review and render loop than as the primary source of truth for mechanical geometry.
   - Done when: Generated parts can be imported into Blender, rendered from canonical views, and attached to a review report.
   - Progress: Added `blender-review` plus `blender_review.py` to write a review JSON, Markdown report, and Blender Python script for front, right, top, and isometric screenshot renders. The command reports when Blender is unavailable instead of pretending screenshots exist.

5. Define Blender's role for aesthetic refinement.
   - Status: Done
   - Why: Blender should help with visual style, decorative surfaces, organic forms, material/color mockups, and "does this look right" checks without undermining parametric mechanical control.
   - Done when: Docs clearly distinguish Blender-as-review/refinement from CadQuery/build123d-as-source-of-truth.
   - Progress: `docs/tooling-references.md`, `docs/generalised-specification.md`, and the Blender review report text now state that Blender is a review/refinement sidecar and not the functional source of truth.

6. Preserve CadQuery/build123d as the mechanical spine.
   - Status: Done
   - Why: Functional printed parts still need repeatable dimensions, tolerances, clearances, walls, fit checks, and printer-aware exports.
   - Done when: The repo has a documented rule for when to use CadQuery, build123d, Blender review, or Blender-first modeling.
   - Progress: `docs/tooling-references.md`, `docs/generalised-specification.md`, and ADR 0002 now route precise mechanical geometry through CadQuery/build123d or CAD Skills, with Blender kept for review and aesthetic feedback unless a part is intentionally decorative or organic.

7. Rebuild mesh-preserved drawers as skin plus functional solids.
   - Status: Done
   - Why: The first mesh-preserved drawer attempts proved source-triangle accounting can pass while Bambu still reports non-manifold parts, open edges, and hundreds of disconnected islands. The preserved artistic mesh must be treated as an immutable exterior skin layer, not as the whole structural solid.
   - Done when: Drawer-front source triangles are selected by front visibility/raycasting, every original source triangle is assigned exactly once, drawer trays/cavities/rails are generated as clean functional solids, skin/backer boundaries are explicitly closed, and the manifest fails if emitted parts are non-manifold.
   - Progress: Added manifest-level geometry-health reporting for open/non-manifold edges, added an optional `front_visible_raycast` skin-selection strategy backed by Open3D when installed, added mesh optional dependencies for the researched v3 stack, added generated inner shells and boundary walls behind preserved source skins, and now emits a Bambu-manifold mesh-preserved print 3MF plus a functional-core diagnostic 3MF for the desk organiser success case.

8. Route clean CAD generation through CAD Skills / text-to-cad when available.
   - Status: Done
   - Why: The upstream CAD Skills workflow is stronger than this repo's local starter renderer for general mechanical CAD because it is build123d/STEP-first, has inspection commands, creates sidecar STL/3MF artifacts, and provides CAD Explorer review links.
   - Done when: Agents default to text-to-cad for new clean mechanical parts, this repo keeps design-contract and printer-handoff ownership, and at least one pilot part proves STEP inspection plus Bambu handoff works end to end.
   - Notes: Do not vendor the upstream toolchain yet. Start with routing rules and an explicit adapter/pilot so this repo does not absorb a large moving skill bundle prematurely.
   - Progress: Added `cad-skills-probe` and `cad-skills-pilot` around `TEXT_TO_CAD_SKILL_DIR`, with dry-run and executable modes for external `scripts/step` and `scripts/inspect`. A live STEP/CAD Explorer pilot is environment-dependent and should be run once a text-to-cad checkout is configured.

## Tooling And Governance Backlog

1. Pin target tool versions.
   - Status: Done
   - Why: CadQuery, build123d, Blender, and MCP APIs can drift; version ambiguity causes broken examples and odd generated geometry.
   - Done when: `pyproject.toml` and docs state the supported tool versions and any known compatibility limits.
   - Progress: Pinned the CAD extra to CadQuery `2.7.x` and build123d `0.10.x`; added compact tooling references for CAD, Blender, Bambu Studio, and MCP.

2. Create repo-owned geometry recipes.
   - Status: Done
   - Why: The repo should keep small trusted patterns instead of copying full upstream docs.
   - Done when: Recipes exist for rounded ramps, shell enclosures, snap/friction lids, keyed seams, jigsaw seams, connectors, filleted wedges, and multi-part plate splits.
   - Progress: Added first-pass recipes for smooth ramps, rounded shells, friction/snap lids, keyed seams, jigsaw seams, and multi-part plate splits.

3. Extend design contracts in briefs.
   - Status: Done
   - Why: Briefs should capture design intent, not just dimensions.
   - Done when: Brief schema supports fields such as silhouette, cross sections, symmetry, surface continuity, max slope, min wall, and visual style.
   - Progress: Added first-pass `design_intent` schema fields and prompt output.

4. Add validation before export.
   - Status: Done
   - Why: CAD scripts should not jump straight from generated code to printer artifacts without checks.
   - Done when: Export commands fail or warn on dimension, bed-fit, alignment, clearance, or geometry-health issues.
   - Progress: Added `validate-design` for pre-generation design-contract completeness and brief-level ramp slope checks. Added `validate-artifacts` for handoff artifact existence, mesh bounds, and known bed-fit checks before Bambu export.

5. Use Blender as review tooling.
   - Status: Done
   - Why: Blender can provide canonical previews, viewport screenshots, visual comparisons, and optional mesh measurement around the existing CAD pipeline.
   - Done when: Blender review is an optional repeatable step that produces artifacts the agent can inspect.
   - Progress: Added the repeatable `blender-review` plan/report/script workflow. The generated report is inspectable even before Blender is installed; screenshots are produced when the command is rerun with an available Blender executable.

6. Keep compact external documentation references.
   - Status: Done
   - Why: Official docs should stay the source of truth, while this repo stores only curated references, pinned versions, and local gotchas.
   - Done when: A concise tooling reference doc links to the official CadQuery, build123d, Blender, Bambu, and MCP docs relevant to this workflow.
   - Progress: Added `docs/tooling-references.md`.

7. Add a thin CAD Skills adapter and pilot workflow.
   - Status: Done
   - Why: Agents need a reliable way to call text-to-cad's `scripts/step`, `scripts/inspect`, and CAD Explorer workflow from this repo without vendoring upstream code or assuming a fixed install path.
   - Done when: The repo can detect a configured CAD Skills install, run one explicit build123d generator through STEP inspection, return CAD Explorer links when available, and pass the resulting artifacts into the existing Bambu handoff path.
   - Suggested shape: use an environment variable such as `TEXT_TO_CAD_SKILL_DIR`, add a wrapper only around explicit targets, and keep text-to-cad as an external tool dependency until a stable release or install contract exists.
   - Progress: Added the `cad_skills.py` adapter, `cad-skills-probe`, and `cad-skills-pilot`. The wrapper detects configured installs, writes JSON reports, extracts CAD Explorer links from command output, and keeps execution behind an explicit `--run`.

## Adjacent MCP Opportunities

- Status: Done for static repo-local resources and common prompts.
- Progress: Added MCP resources for the backlog, geometry recipes, starter brief, and Bambu A1 handoff example. Added prompts for "review generated part", "prepare Bambu handoff", and "validate design contract".
- Deferred: Durable task handling for long-running Bambu and Blender operations should wait until the local server is ready to target a newer MCP protocol revision.
