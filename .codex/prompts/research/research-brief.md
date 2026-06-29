# Research Brief Prompt

Use this prompt before dispatching source-specific research agents.

## Goal

Create a bounded research brief that tells each source agent what to look for,
which sources are allowed, what output is needed, and what must not be changed.

## Inputs

- Repository or product area.
- Research question.
- Desired output target: backlog, review, architecture, design, ADR, risk, or
  task-packet candidates.
- Allowed source families: GitHub, arXiv, Hacker News, official docs,
  standards, vendor docs, forums/social, local repo.
- Exact search plan per source: seed URLs or domains, search queries,
  inclusion terms, exclusion terms, artifact types, source-count limits, and
  evidence quality floor.
- Time sensitivity and source-quality expectations.

## Source Planning Rule

Do not let a source agent improvise broad web searches. If the brief lacks
enough detail for a source family, mark that source as `blocked` or ask for a
brief refinement instead of searching randomly.

Every source entry must answer:

- why this source family is useful for this question
- where the agent is allowed to look
- which exact queries or seed URLs to use first
- what artifact types count as evidence
- how many sources are enough
- what should be ignored
- what quality floor is required before the evidence can affect backlog,
  review, architecture, design, ADR, risk, or task-packet proposals

## Default Source Budgets

Use these defaults unless the human gives a narrower plan:

| Source | Start From | Evidence To Prefer | Budget |
| --- | --- | --- | --- |
| GitHub | named repos, orgs, topics, or exact code/search queries | maintained repos, examples, issues, PRs, releases, docs | 5-15 candidate artifacts; shortlist 3-7 |
| arXiv | exact topic queries and known paper titles/authors | recent papers, surveys, papers with code/evals, seminal older papers | 5-12 papers; shortlist 3-6 |
| Hacker News | Algolia/HN item search with exact terms | discussions with concrete failure modes and linked primary sources | 5-12 threads; shortlist 3-5 leads |
| Official docs | official domains, standards bodies, primary repositories | versioned docs, specs, release notes, API references | 3-10 primary docs; capture version/date |

## Required Boundary

- Use the `browser-research` trust profile unless a stricter local profile is
  selected.
- Keep the run read-only.
- Do not post, like, bookmark, follow, vote, DM, comment, submit forms, accept
  terms, bypass access controls, or mutate any account.
- Do not write backlog rows, ADRs, source docs, issue comments, or code. Produce
  proposals only.
- If a source requires authentication, record that authenticated viewing was
  used and summarize private content instead of copying it wholesale.
- Do not use general Google or broad web search unless the source entry
  explicitly permits `other` sources or names search-engine discovery as the
  first step.

## Output

Return JSON matching `schemas/research-brief.schema.json`.

Use this shape:

```json
{
  "schema_version": 1,
  "research": {
    "id": "RESEARCH-001",
    "title": "Short title",
    "question": "What should the agents discover?",
    "repo_context": ["Relevant files, docs, ADRs, product areas, or constraints"]
  },
  "sources": [
    {
      "source_type": "github",
      "purpose": "Find implementation patterns for bounded research runners.",
      "query": "repo-contract research agent source-specific prompts",
      "scope": "What this source agent should and should not cover",
      "allowed_domains": ["github.com"],
      "seed_urls": ["https://github.com/example/project"],
      "search_queries": ["repo-contract research agent", "agent workflow research runner"],
      "include_terms": ["prompt", "schema", "evidence", "source report"],
      "exclude_terms": ["marketing-only", "unmaintained"],
      "required_artifact_types": ["repo", "docs", "issue", "pull-request", "release"],
      "min_results": 5,
      "max_results": 15,
      "quality_floor": "medium",
      "freshness": "Prefer active projects with commits or releases in the last 18 months unless the project is a stable reference."
    }
  ],
  "boundaries": {
    "trust_profile": "browser-research",
    "read_only": true,
    "forbidden_actions": ["account mutation", "source writes", "backlog writes"],
    "source_quality_rules": ["Treat social/forum content as leads unless backed by primary evidence."]
  },
  "outputs": {
    "target": "backlog",
    "artifact_dir": ".agent-workflows/runs/<run-id>/research",
    "success_criteria": ["Each source report has URLs, retrieval dates, caveats, and ranked proposals."]
  },
  "approval": {
    "human_approval_required": true,
    "proposed_writes_only": true
  }
}
```
