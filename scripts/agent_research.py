#!/usr/bin/env python3
"""Create local targeted-research artifacts for source-specific agent runs."""

import argparse
from datetime import datetime, timezone
import json
import subprocess
from pathlib import Path


SOURCE_PROMPTS = {
    "github": ".codex/prompts/research/source-github.md",
    "arxiv": ".codex/prompts/research/source-arxiv.md",
    "hacker-news": ".codex/prompts/research/source-hacker-news.md",
    "official-docs": ".codex/prompts/research/source-official-docs.md",
}

SOURCE_ALIASES = {
    "hn": "hacker-news",
    "hackernews": "hacker-news",
    "official": "official-docs",
    "docs": "official-docs",
}
VALID_SOURCES = set(SOURCE_PROMPTS)

SOURCE_DEFAULTS = {
    "github": {
        "purpose": "Find maintained implementation patterns and project examples.",
        "required_artifact_types": ["repo", "docs", "issue", "pull-request", "release"],
        "min_results": 5,
        "quality_floor": "medium",
        "allowed_domains": ["github.com"],
    },
    "arxiv": {
        "purpose": "Find paper-backed architecture, method, or evaluation ideas.",
        "required_artifact_types": ["paper"],
        "min_results": 3,
        "quality_floor": "medium",
        "allowed_domains": ["arxiv.org"],
    },
    "hacker-news": {
        "purpose": "Find practitioner pain signals and linked primary-source leads.",
        "required_artifact_types": ["thread", "comment"],
        "min_results": 3,
        "quality_floor": "lead",
        "allowed_domains": ["news.ycombinator.com", "hn.algolia.com"],
    },
    "official-docs": {
        "purpose": "Find high-confidence primary documentation and versioned facts.",
        "required_artifact_types": ["docs", "standard", "api-reference", "release"],
        "min_results": 3,
        "quality_floor": "high",
        "allowed_domains": [],
    },
}


def git_output(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def repo_root():
    return Path(git_output(["rev-parse", "--show-toplevel"], Path.cwd())).resolve()


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_required_text(root: Path, rel_path: str):
    path = root / rel_path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(
            f"Missing prompt file: {rel_path}. Install the review-prompts profile or the agentic preset."
        ) from exc


def normalize_source(value):
    raw = (value or "github").strip().lower()
    source = SOURCE_ALIASES.get(raw, raw)
    if source not in VALID_SOURCES:
        available = ", ".join(sorted(VALID_SOURCES | set(SOURCE_ALIASES)))
        raise SystemExit(f"Unknown research source: {value}. Available sources: {available}")
    return source


def split_csv(value, default):
    raw = value or default
    return [item.strip() for item in raw.split(",") if item.strip()]


def unique_run_dir(root):
    runs_root = root / ".agent-workflows" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    base = f"{timestamp()}-research"
    candidate = runs_root / base
    suffix = 2
    while candidate.exists():
        candidate = runs_root / f"{base}-{suffix}"
        suffix += 1
    return candidate


def latest_research_dir(root):
    runs_root = root / ".agent-workflows" / "runs"
    candidates = []
    if runs_root.is_dir():
        for run_dir in runs_root.iterdir():
            research_dir = run_dir / "research"
            if (research_dir / "research-run.json").exists():
                candidates.append(research_dir)
    if not candidates:
        raise SystemExit("No research run found. Run `make agent-research-plan` first.")
    return sorted(candidates)[-1]


def source_template(source, args):
    defaults = SOURCE_DEFAULTS.get(source, {})
    queries = split_csv(args.query, "")
    return {
        "source_type": source,
        "purpose": defaults.get("purpose", "Answer the research brief from this source family."),
        "query": args.query or f"Research {source} for the brief question.",
        "scope": args.scope or "Stay within the research brief and source-specific prompt.",
        "allowed_domains": defaults.get("allowed_domains", []),
        "seed_urls": [],
        "search_queries": queries or [args.query or f"{source} research brief query"],
        "include_terms": [],
        "exclude_terms": [],
        "required_artifact_types": defaults.get("required_artifact_types", ["other"]),
        "min_results": defaults.get("min_results", 1),
        "max_results": args.max_results,
        "quality_floor": defaults.get("quality_floor", "medium"),
        "freshness": None,
        "allow_general_web": False,
    }


def novelty_ledger_template():
    return {
        "carry_forward_leads": [],
        "novelty_threshold": 70,
        "prior_question_fingerprints": [],
        "recent_topics": [],
    }


def candidate_score_template():
    return {
        "effort": 0,
        "evidence_strength": 0,
        "fit": 0,
        "novelty": 0,
        "rationale": "Not scored yet.",
        "recommendation_state": "defer",
        "risk": 0,
    }


def plan(args):
    root = repo_root()
    prompt = read_required_text(root, ".codex/prompts/research/research-brief.md")
    research_dir = unique_run_dir(root) / "research"
    research_dir.mkdir(parents=True)
    sources = [normalize_source(source) for source in split_csv(args.sources, "github,arxiv,hacker-news,official-docs")]
    research_id = args.research_id or research_dir.parent.name

    brief = {
        "schema_version": 1,
        "approval": {"human_approval_required": True, "proposed_writes_only": True},
        "boundaries": {
            "forbidden_actions": [
                "account mutation",
                "source writes",
                "backlog writes",
                "ADR writes",
                "issue or PR mutation",
            ],
            "read_only": True,
            "source_quality_rules": [
                "Prefer primary sources for factual claims.",
                "Treat GitHub examples as implementation leads until license and fit are checked.",
                "Treat forum and social sources as leads unless backed by primary evidence.",
            ],
            "trust_profile": "browser-research",
        },
        "outputs": {
            "artifact_dir": str(research_dir.relative_to(root)),
            "success_criteria": [
                "Each source agent writes a source report with URLs, retrieval dates, evidence grades, and caveats.",
                "Synthesis produces proposals only; humans approve any backlog, docs, ADR, issue, or code writes.",
            ],
            "target": args.output,
        },
        "novelty_ledger": novelty_ledger_template(),
        "research": {
            "created_at": now(),
            "id": research_id,
            "question": args.question or "Fill in the precise research question before dispatch.",
            "repo_context": split_csv(args.context, ""),
            "requested_by": "local-agent",
            "title": args.title or "Targeted research",
        },
        "sources": [source_template(source, args) for source in sources],
    }
    run_payload = {
        "schema_version": 1,
        "created_at": now(),
        "research_id": research_id,
        "status": "planned",
        "sources": sources,
        "target": args.output,
        "artifacts": {
            "brief": "research-brief.template.json",
            "source_reports": "sources/<source>/source-report.template.json",
            "synthesis": "synthesis/research-synthesis.template.json",
        },
    }

    write_json(research_dir / "research-brief.template.json", brief)
    write_json(research_dir / "research-run.json", run_payload)
    (research_dir / "research-brief.prompt.md").write_text(prompt, encoding="utf-8")
    print(f"Research plan written: {research_dir.relative_to(root)}")
    print("Next: make agent-research-run RESEARCH_SOURCE=github")


def run_source(args):
    root = repo_root()
    research_dir = latest_research_dir(root)
    source = normalize_source(args.source)
    source_dir = research_dir / "sources" / source
    source_dir.mkdir(parents=True, exist_ok=True)

    run_payload = json.loads((research_dir / "research-run.json").read_text(encoding="utf-8"))
    report = {
        "schema_version": 1,
        "caveats": [],
        "disposition": {
            "follow_up_needed": [],
            "status": "not-run",
            "summary": "Fill this after the source agent completes.",
        },
        "findings": [],
        "queries": [args.query] if args.query else [],
        "run": {
            "agent_id": f"source-{source}",
            "completed_at": None,
            "research_id": run_payload["research_id"],
            "started_at": now(),
        },
        "source": {
            "authenticated": False,
            "deviations": [],
            "search_plan_followed": False,
            "scope": args.scope or "Use the research brief scope.",
            "source_type": source,
        },
        "sources_visited": [],
    }

    prompt_rel = SOURCE_PROMPTS[source]
    source_prompt = read_required_text(root, prompt_rel)
    brief_rel = (research_dir / "research-brief.template.json").relative_to(root)
    report_rel = (source_dir / "source-report.template.json").relative_to(root)
    prompt_text = f"""# Source Research Dispatch: {source}

Research brief: `{brief_rel}`
Source report template: `{report_rel}`

Run boundary:
- Stay read-only.
- Do not mutate accounts, repos, issues, PRs, docs, backlog, ADRs, or code.
- Write findings into the source report template only after the run is complete.

---

{source_prompt}
"""
    write_json(source_dir / "source-report.template.json", report)
    (source_dir / "prompt.md").write_text(prompt_text, encoding="utf-8")
    print(f"Source research prompt written: {source_dir.relative_to(root) / 'prompt.md'}")


def synthesize(args):
    root = repo_root()
    research_dir = latest_research_dir(root)
    prompt = read_required_text(root, ".codex/prompts/research/research-synthesis.md")
    run_payload = json.loads((research_dir / "research-run.json").read_text(encoding="utf-8"))
    synthesis_dir = research_dir / "synthesis"
    synthesis_dir.mkdir(parents=True, exist_ok=True)
    source_artifacts = []
    sources_dir = research_dir / "sources"
    if sources_dir.is_dir():
        source_artifacts = sorted(str(path.relative_to(root)) for path in sources_dir.glob("*/source-report.template.json"))
    payload = {
        "schema_version": 1,
        "candidate_ideas": [
            {
                "candidate_score": candidate_score_template(),
                "id": "CANDIDATE-001",
                "proposed_artifact": "",
                "source_evidence": [],
                "state": "draft",
                "target": run_payload.get("target", "backlog"),
                "title": "Fill in candidate idea after synthesis.",
            }
        ],
        "disposition": {
            "next_actions": [],
            "status": "not-run",
            "summary": "Fill this after synthesis.",
        },
        "proposals": [],
        "rejected_leads": [],
        "run": {
            "brief": str((research_dir / "research-brief.template.json").relative_to(root)),
            "research_id": run_payload["research_id"],
            "source_artifacts": source_artifacts,
            "synthesized_at": None,
        },
        "source_plan_audit": [],
        "source_reports": source_artifacts,
        "summary": ["Fill this after reading source reports."],
    }
    write_json(synthesis_dir / "research-synthesis.template.json", payload)
    (synthesis_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    print(f"Research synthesis prompt written: {synthesis_dir.relative_to(root) / 'prompt.md'}")


def to_task_packet(args):
    root = repo_root()
    research_dir = latest_research_dir(root)
    prompt = read_required_text(root, ".codex/prompts/research/research-to-backlog.md")
    task_packet = read_required_text(root, ".codex/prompts/task-packet.md")
    handoff_dir = research_dir / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    synthesis_path = research_dir / "synthesis" / "research-synthesis.template.json"
    handoff = f"""# Research To Task Packet Handoff

Research synthesis: `{synthesis_path.relative_to(root)}`

Use the research-to-work prompt first. If a proposal is accepted for
implementation, use the task-packet prompt to produce executable scope.

---

{prompt}

---

{task_packet}
"""
    (handoff_dir / "research-to-task-packet.prompt.md").write_text(handoff, encoding="utf-8")
    print(f"Research handoff prompt written: {handoff_dir.relative_to(root) / 'research-to-task-packet.prompt.md'}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--title", default="")
    plan_parser.add_argument("--question", default="")
    plan_parser.add_argument("--context", default="")
    plan_parser.add_argument("--sources", default="github,arxiv,hacker-news,official-docs")
    plan_parser.add_argument("--output", default="backlog", choices=["backlog", "review", "architecture", "design", "adr", "risk", "task-packet"])
    plan_parser.add_argument("--research-id", default="")
    plan_parser.add_argument("--query", default="")
    plan_parser.add_argument("--scope", default="")
    plan_parser.add_argument("--max-results", type=int, default=20)
    plan_parser.set_defaults(func=plan)

    source_parser = subparsers.add_parser("run")
    source_parser.add_argument("--source", default="github")
    source_parser.add_argument("--query", default="")
    source_parser.add_argument("--scope", default="")
    source_parser.add_argument("--max-results", type=int, default=20)
    source_parser.set_defaults(func=run_source)

    synth_parser = subparsers.add_parser("synthesize")
    synth_parser.set_defaults(func=synthesize)

    handoff_parser = subparsers.add_parser("to-task-packet")
    handoff_parser.set_defaults(func=to_task_packet)

    return parser.parse_args()


def main():
    args = parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
