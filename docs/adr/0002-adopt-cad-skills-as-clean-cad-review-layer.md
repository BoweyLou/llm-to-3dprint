# ADR 0002: Adopt CAD Skills As Clean CAD Review Layer

- Status: Proposed
- Date: 2026-05-21

## Context

This repo already owns a structured design-brief workflow, pre-generation design-contract checks, Bambu handoff tooling, and mesh-preserved workflows for existing artistic 3MF sources. Its local script renderer is intentionally narrow and currently strongest for rectangular CadQuery enclosure starters.

The external `earthtojake/text-to-cad` CAD Skills bundle provides a stronger general clean-CAD loop: build123d source, STEP-first generation, geometry inspection, sidecar STL/3MF exports, CAD Explorer review, and stable `@cad[...]` references for follow-up edits.

## Decision

Use CAD Skills / text-to-cad as the preferred external generation and review layer for new clean mechanical CAD when it is installed.

Keep this repo responsible for:

- design-brief and design-intent contracts
- mesh-preserved source-3MF jobs
- Bambu handoff, seed-template, and printer-native project workflows
- repo-specific documentation governance and backlog tracking

Do not vendor the upstream skill bundle yet. Start with routing rules, a pilot workflow, and a thin adapter around explicit CAD Skills targets once the install path and command contract are stable.

## Consequences

General clean CAD work can use better STEP inspection and CAD Explorer review without forcing this repo to rebuild those capabilities.

The local CadQuery renderer remains useful as a starter and fallback, but it should not be stretched into a general CAD engine.

The repo gains one external workflow dependency for best results. Agents must report when CAD Skills is unavailable and fall back to the local brief, prompt, renderer, or custom-script path.

## Alternatives considered

- Replace this repo with text-to-cad: rejected because text-to-cad does not cover this repo's Bambu and mesh-preserved workflows.
- Vendor text-to-cad: rejected for now because the upstream toolchain is a large moving skill bundle rather than a pinned library dependency.
- Keep building generic CAD tooling here: rejected as the default direction because it duplicates stronger upstream capabilities and distracts from printer-specific orchestration.
