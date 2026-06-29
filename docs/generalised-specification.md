# Parametric CAD Generation with Python and LLMs

## Overview

This document generalizes the "LLM -> code -> printable geometry" workflow into a reusable method for generating enclosures and other 3D objects with Python-based CAD tools.

The intended split of responsibility is:

- The LLM interprets natural-language requirements, plans the model structure, and generates or edits Python code.
- A Python CAD library handles geometric construction and export.
- The user reviews geometry, fit, and printability, then iterates.

This approach is useful for electronics housings, storage boxes, fixtures, decorative objects, and any other part that benefits from parameterized design.

## Problem Statement

The goal is to create 3D-printable objects tailored to a specific device or use case while retaining parametric control.

Common requirements include:

- internal fit and clearances
- openings, mounting points, ventilation, or access features
- hard mesh-preservation requirements where an existing 3MF surface must remain in the output
- printable geometry with reasonable overhangs
- iteration through natural language without losing code-based editability

Python is a strong vehicle for this workflow because libraries such as CadQuery and build123d allow feature-based scripting with OpenCascade-backed BREP geometry and export to standard formats such as STL and STEP.

## Tools and Environment

### Python CAD Library

Use a script-based parametric CAD library:

- `cadquery` for concise feature-based mechanical modeling
- `build123d` when you want a Pythonic BREP workflow with strong topology handling

When the CAD Skills / text-to-cad skill bundle is installed, use it as the preferred clean-CAD generation and inspection layer for new mechanical parts. It keeps STEP as the primary artifact, generates sidecar STL/3MF outputs from the same source, exposes geometry inspection commands, and provides CAD Explorer links for visual review. This repo then remains responsible for the surrounding design contract, mesh-preserved workflows, and printer-specific Bambu handoff.

### Python Runtime

Use Python 3.10+ for the core repo. The CAD extra is pinned to the current supported CadQuery/build123d minor release families; see [tooling-references.md](tooling-references.md) before changing those ranges.

Suggested packages:

- `cadquery`
- `build123d`
- `numpy`
- `matplotlib`
- an optional viewer such as CQ-Editor or Jupyter-CadQuery

### Model Viewer

Inspect geometry in CQ-Editor, Jupyter, or an external CAD viewer after exporting STEP/STL.

For text-to-cad-generated parts, prefer CAD Explorer as the first visual review tool. It provides quick browser review of STEP, STL, 3MF, DXF, and related artifacts and can surface stable geometry references for follow-up edits.

Use Blender as an optional review tool for canonical screenshots, visual comparison, and scene-level measurements. Blender should feed observations back into the parametric CAD script rather than becoming the source of truth for functional dimensions.

### LLM

Use the LLM as a planner and code generator, not as a geometric authority. Expect to iterate after reviewing the model.

## Workflow

### 1. Gather Parameters

Define:

- object purpose
- overall external dimensions
- internal clearances
- wall and floor thicknesses
- feature locations and sizes
- print orientation and support constraints
- access requirements such as lids, hinges, or fasteners
- design intent such as silhouette, visual style, symmetry, surface continuity, smoothness, forbidden features, cross-section expectations, max slope, and minimum wall constraints
- for mesh-preserved work, source mesh path, reuse policy, triangle-accounting requirement, drawer/insert masks, and target clearances

The design intent is a contract. It should prevent shape drift such as isolated bumps, asymmetric side profiles, accidental decorative features, or abrupt transitions that technically satisfy the dimensions but fail the intended form.

Before generating CAD, run:

```bash
python3 -m llm_to_3dprint.cli validate-design path/to/brief.json
```

The first-pass validator checks contract completeness and brief-level shape risks such as ramp slope. See [geometry-recipes.md](geometry-recipes.md) for the local recipe expectations behind those checks.

For mesh-preserved drawer work, run the partitioner after validation:

```bash
python3 -m llm_to_3dprint.cli build-mesh-drawers path/to/brief.json --output-dir generated/output/my_mesh_drawers
python3 -m llm_to_3dprint.cli validate-mesh-manifest generated/output/my_mesh_drawers/my_mesh_drawers_mesh_manifest.json
```

This workflow treats the source 3MF triangles as the visible artifact to preserve and adds generated geometry only for shell thickness, backing, cavities, rails, and drawer trays. Source-triangle accounting is a required audit, but the manifest must also report slicer-closed geometry health for the mesh-preserved print output; open edges or Bambu-reported non-manifold parts are failures even when every source triangle is assigned exactly once.

### 2. Generate Python CAD Code with the LLM

Prompt the LLM with:

- object type
- key dimensions
- coordinate conventions
- design intent contract
- required features
- target library
- export requirements
- a request for fully parameterized code

For general clean CAD work, route generation through text-to-cad when available:

- convert the user request and local design contract into a concise CAD brief
- generate or edit build123d source that exposes `gen_step()`
- generate STEP as the primary artifact
- run geometry inspection against the STEP output
- create STL/3MF sidecars only after STEP generation succeeds
- use CAD Explorer for first-pass visual review

This repo keeps that external dependency behind a thin adapter. Use
`cad-skills-probe` to verify `TEXT_TO_CAD_SKILL_DIR`, then use
`cad-skills-pilot --generator <file> --output-dir <dir>` for an explicit pilot.
The pilot writes a report even when run as a dry run, and only executes the
external `scripts/step` and `scripts/inspect` commands when `--run` is passed.

The generated script should:

- define all critical dimensions as variables
- build the main solid from primitives
- add or subtract features using relative references when possible
- export STL and STEP

### 3. Execute and Validate

- run the script in Python
- correct syntax or API errors
- inspect the solid visually
- adjust parameters and rerun
- verify the model remains stable when dimensions change
- validate final artifacts against the intended dimensions in the target slicer or printer tool when available
- compare the result against the design intent before accepting it as printable output

For Bambu handoffs, run `validate-artifacts` against the project spec before
exporting. It checks that referenced artifacts exist, computes mesh bounds for
STL/OBJ/3MF files when possible, and fails parts that exceed known build volumes
such as Bambu A1 and A1 mini. STEP files are checked for existence and header
shape; detailed STEP bounds remain the responsibility of CAD Skills inspection
or a CAD kernel.

For visual review, run `blender-review` to write a repeatable Blender plan,
Markdown report, and Python render script for canonical front, right, top, and
isometric screenshots. Blender is a review/refinement sidecar; the CAD script,
design brief, and handoff spec remain the source of truth for functional
dimensions.

### 4. Print and Iterate

- export STL for slicing
- test critical fit features with small prints
- print the full part once interfaces are validated
- adjust parameters and regenerate when needed

## Best Practices

- parameterize every dimension that may change
- treat dimension edits as dependency edits: recompute derived slopes, landings, connector positions, traction features, bed fit, and clearances
- prefer relative references over brittle absolute placement
- choose BREP tooling for precise mechanical parts
- export STEP for interoperability
- document units and coordinate conventions
- use assertions or lightweight tests for obvious geometry assumptions
- specify silhouette and cross-section expectations before generating complex geometry
- reject decorative or support features that violate the design intent contract
- run `validate-design` before prompt generation on non-trivial briefs
- run `validate-artifacts` before Bambu export when a handoff spec references generated geometry
- use `blender-review` for screenshot planning when visual review is needed
- store scripts in version control
- generate printer-ready 3MF files from current parametric geometry, not stale STL intermediates
- for mesh-preserved jobs, preserve source triangle identity and prove every source triangle is assigned exactly once
- keep assembly STEP export optional when the immediate deliverable is plate-ready STL or 3MF output
- for functional ramps and contact parts, report ratios such as slope after major dimension changes so printability and usability risks are visible

## Expectations for an AI Agent

An implementation-focused agent should:

- capture the design brief in structured form
- preserve the design intent contract through code generation and edits
- default to the text-to-cad build123d/STEP-first workflow when the skill is installed and the task is clean mechanical CAD
- use `cad-skills-probe` and `cad-skills-pilot` to make the external text-to-cad handoff explicit
- use this repo's local CadQuery renderer only for supported rectangular enclosure starter scripts
- keep mesh-preserved source-3MF jobs inside this repo's mesh workflow
- keep Bambu-native project output inside this repo's Bambu handoff workflow
- generate commented, parameterized Python code
- run validation locally when possible
- preserve and edit the same script through iterations instead of rewriting from scratch
- hand back the Python source and exported model files

## Limitations

- LLMs can misread spatial relationships
- generated code may be syntactically valid but geometrically wrong
- geometry should always be reviewed before printing
- test prints are still necessary for functional parts

## Conclusion

Combining LLM planning with Python CAD libraries gives you a practical path from natural language to editable, printable parametric models. The real leverage comes from keeping the workflow structured: explicit briefs, repeatable prompt patterns, executable scripts, and fast iteration.
