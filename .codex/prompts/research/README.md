# Targeted Research Workflows

Use these prompts when a repo, product area, review, backlog, or architecture
question needs source-specific research before implementation.

The workflow is evidence-first:

1. Write a research brief.
2. Dispatch one source agent per source family.
3. Capture one source report per agent.
4. Synthesize findings into proposed backlog, review, design, ADR, risk, or
   task-packet outputs.
5. Ask for human approval before changing source docs, backlog rows, ADRs, or
   implementation files.

The brief is also the anti-random-search contract. It must name seed URLs or
exact queries, allowed domains, inclusion/exclusion terms, result budgets,
artifact types, and evidence quality floors for each source family. If those are
missing, the source agent should stop and ask for a narrower brief instead of
searching broadly.

## Prompts

- `research-brief.md`: Define the research question, allowed sources, output
  target, trust profile, and stop conditions.
- `source-github.md`: Collect implementation patterns from public repositories,
  issues, pull requests, discussions, and release notes.
- `source-arxiv.md`: Collect paper-backed architecture, method, evaluation, or
  algorithm ideas.
- `source-hacker-news.md`: Collect practitioner pain signals and architecture
  leads from Hacker News discussions.
- `source-official-docs.md`: Collect high-confidence facts from official docs,
  standards, release notes, and primary repositories.
- `research-synthesis.md`: Deduplicate source reports and rank evidence-backed
  proposals.
- `research-to-backlog.md`: Convert accepted research proposals into backlog,
  review, design, ADR, risk, or task-packet candidates.

## Source Quality

Use official docs, standards, primary repositories, and papers as claim-bearing
evidence. Use GitHub examples as implementation leads that still need license,
maintenance, and fit checks. Use Hacker News, forums, social posts, and vendor
marketing as weak signals unless backed by primary evidence.

## Output Contracts

- Research briefs should conform to `schemas/research-brief.schema.json`.
- Source reports should conform to `schemas/research-source-report.schema.json`.
- Syntheses should conform to `schemas/research-synthesis.schema.json`.
