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
- printable geometry with reasonable overhangs
- iteration through natural language without losing code-based editability

Python is a strong vehicle for this workflow because libraries such as CadQuery and build123d allow feature-based scripting with OpenCascade-backed BREP geometry and export to standard formats such as STL and STEP.

## Tools and Environment

### Python CAD Library

Use a script-based parametric CAD library:

- `cadquery` for concise feature-based mechanical modeling
- `build123d` when you want a Pythonic BREP workflow with strong topology handling

### Python Runtime

Use Python 3.10+.

Suggested packages:

- `cadquery`
- `build123d`
- `numpy`
- `matplotlib`
- an optional viewer such as CQ-Editor or Jupyter-CadQuery

### Model Viewer

Inspect geometry in CQ-Editor, Jupyter, or an external CAD viewer after exporting STEP/STL.

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

### 2. Generate Python CAD Code with the LLM

Prompt the LLM with:

- object type
- key dimensions
- coordinate conventions
- required features
- target library
- export requirements
- a request for fully parameterized code

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

### 4. Print and Iterate

- export STL for slicing
- test critical fit features with small prints
- print the full part once interfaces are validated
- adjust parameters and regenerate when needed

## Best Practices

- parameterize every dimension that may change
- prefer relative references over brittle absolute placement
- choose BREP tooling for precise mechanical parts
- export STEP for interoperability
- document units and coordinate conventions
- use assertions or lightweight tests for obvious geometry assumptions
- store scripts in version control

## Expectations for an AI Agent

An implementation-focused agent should:

- capture the design brief in structured form
- default to CadQuery unless the part demands something else
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

