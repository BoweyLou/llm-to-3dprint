#!/usr/bin/env python3
"""Classify review risk from changed repository paths."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# Script flow:
# 1. Collect changed paths from arguments or the current git working tree.
# 2. Match each path against deterministic risk rules.
# 3. Collapse rule matches into a risk tier, trust profile, and reviewer roster.
# 4. Emit JSON or a concise text summary for local review startup.
#
# Function guide:
# - working_tree_paths/normalize_paths collect and dedupe file paths.
# - match_rules/classify_paths apply stable path and keyword heuristics.
# - risk_tier/trust_profile/recommended_personas collapse matches into guidance.
# - parse_args/main drive the CLI.


@dataclass(frozen=True)
class RiskRule:
    id: str
    tier: str
    personas: tuple[str, ...]
    patterns: tuple[str, ...]
    reason: str


TIER_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

BASE_PERSONAS = (
    "doc-code-delta",
    "ai-code-slop",
    "test-behavior-risk",
    "reuse-architecture",
)

RULES = (
    RiskRule(
        id="auth-or-secrets",
        tier="high",
        personas=("security-privacy", "test-behavior-risk"),
        patterns=("auth", "login", "session", "permission", "secret", "token", "credential", ".env"),
        reason="auth, permission, token, credential, or secret-handling path",
    ),
    RiskRule(
        id="data-deletion-or-destructive",
        tier="critical",
        personas=("security-privacy", "api-data-contracts", "test-behavior-risk"),
        patterns=("delete", "destroy", "purge", "truncate", "wipe", "drop", "reset"),
        reason="destructive data operation path or name",
    ),
    RiskRule(
        id="migration-or-persistence",
        tier="high",
        personas=("api-data-contracts", "test-behavior-risk"),
        patterns=("migration", "migrations/", "database", "db/", "schema", "schemas/", ".sql", "model"),
        reason="migration, schema, database, or persisted data path",
    ),
    RiskRule(
        id="public-api-or-contract",
        tier="high",
        personas=("api-data-contracts", "doc-code-delta", "test-behavior-risk"),
        patterns=("api/", "openapi", "graphql", "webhook", "contract", "public", "sdk", "client"),
        reason="public API, generated client, webhook, or contract path",
    ),
    RiskRule(
        id="ci-build-release",
        tier="medium",
        personas=("dependencies-build", "runtime-observability"),
        patterns=(
            ".github/workflows",
            "ci/",
            "build",
            "release",
            "dockerfile",
            "containerfile",
            "makefile",
            "package.json",
            "pyproject.toml",
            "requirements",
        ),
        reason="CI, build, packaging, or release path",
    ),
    RiskRule(
        id="runtime-or-ops",
        tier="medium",
        personas=("runtime-observability",),
        patterns=("deploy", "infra", "terraform", "helm", "service", "scheduler", "cron", "runbook", "ops/"),
        reason="runtime, deployment, scheduling, or operations path",
    ),
    RiskRule(
        id="docs-contract",
        tier="medium",
        personas=("doc-code-delta",),
        patterns=("agents.md", "review.md", "doc-contract", "documentation-contract", "adr/", "docs/adr"),
        reason="agent instruction, docs contract, or ADR path",
    ),
    RiskRule(
        id="frontend-user-flow",
        tier="medium",
        personas=("frontend-ux", "test-behavior-risk"),
        patterns=("frontend", "components/", "pages/", "routes/", ".tsx", ".jsx", ".vue", ".svelte", ".css"),
        reason="frontend or user-flow path",
    ),
)


def normalize_paths(paths: list[str]) -> list[str]:
    normalized = []
    for path in paths:
        value = path.strip().replace("\\", "/")
        if " -> " in value:
            value = value.split(" -> ", 1)[1].strip()
        if value:
            normalized.append(value)
    return sorted(set(normalized))


def working_tree_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "git status failed")
    paths = []
    for line in result.stdout.splitlines():
        if line:
            paths.append(line[3:].strip())
    return normalize_paths(paths)


def match_rules(path: str) -> list[RiskRule]:
    lowered = path.lower()
    return [rule for rule in RULES if any(pattern in lowered for pattern in rule.patterns)]


def risk_tier(matches: list[dict[str, str]]) -> str:
    if not matches:
        return "low"
    return max((match["tier"] for match in matches), key=lambda tier: TIER_ORDER[tier])


def trust_profile(tier: str, matches: list[dict[str, str]]) -> str:
    rule_ids = {match["rule_id"] for match in matches}
    if "auth-or-secrets" in rule_ids or "data-deletion-or-destructive" in rule_ids:
        return "untrusted-pr" if tier == "critical" else "read-only-review"
    return "read-only-review"


def recommended_personas(matches: list[dict[str, str]]) -> list[str]:
    personas = list(BASE_PERSONAS)
    for match in matches:
        for persona in match["personas"]:
            if persona not in personas:
                personas.append(persona)
    return personas


def classify_paths(paths: list[str]) -> dict[str, object]:
    changed_paths = normalize_paths(paths)
    matches: list[dict[str, object]] = []
    for path in changed_paths:
        for rule in match_rules(path):
            matches.append(
                {
                    "path": path,
                    "rule_id": rule.id,
                    "tier": rule.tier,
                    "reason": rule.reason,
                    "personas": list(rule.personas),
                }
            )

    tier = risk_tier(matches)  # type: ignore[arg-type]
    return {
        "schema_version": 1,
        "changed_files": changed_paths,
        "risk_tier": tier,
        "trust_profile": trust_profile(tier, matches),  # type: ignore[arg-type]
        "recommended_personas": recommended_personas(matches),  # type: ignore[arg-type]
        "triggers": matches,
        "guidance": guidance(tier, matches),  # type: ignore[arg-type]
    }


def guidance(tier: str, matches: list[dict[str, str]]) -> list[str]:
    notes = [
        "Reviewers are read-only by default: no file writes, git staging, commits, pushes, PR mutation, account mutation, or non-allowlisted network calls.",
    ]
    if tier in {"high", "critical"}:
        notes.append("Use specialist reviewers and require concrete file, command, or runtime evidence before accepting findings.")
    if any(match["rule_id"] == "auth-or-secrets" for match in matches):
        notes.append("Do not expose secrets, tokens, cookies, private URLs, request bodies, or personal data in prompts or receipts.")
    if any(match["rule_id"] == "data-deletion-or-destructive" for match in matches):
        notes.append("Require human approval and explicit rollback or recovery evidence before any write-capable follow-up.")
    if not matches:
        notes.append("No high-risk path trigger matched; keep the default small reviewer set unless the user request widens scope.")
    return notes


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="changed paths to classify")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root for --working-tree")
    parser.add_argument("--working-tree", action="store_true", help="classify paths from git status --porcelain")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or [])
    paths = working_tree_paths(args.root) if args.working_tree else normalize_paths(args.paths)
    result = classify_paths(paths)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"risk tier: {result['risk_tier']}")
        print(f"trust profile: {result['trust_profile']}")
        print("recommended personas: " + ", ".join(result["recommended_personas"]))  # type: ignore[index]
        for trigger in result["triggers"]:  # type: ignore[index]
            print(f"- {trigger['path']}: {trigger['rule_id']} ({trigger['tier']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
