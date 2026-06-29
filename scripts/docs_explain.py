#!/usr/bin/env python3
"""Explain target repository docs with deterministic local citations."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_QUESTION = (
    "What do the repository docs say about documentation impact, docs waivers, "
    "and requesting documentation patches?"
)
DEFAULT_MAX_RESULTS = 5
DEFAULT_SNIPPET_LINES = 4
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".rst", ".json", ".yaml", ".yml"}
ROOT_DOC_FILENAMES = {
    "README.md",
    "AGENTS.md",
    "REVIEW.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "doc-contract.json",
}
DEFAULT_DOC_PREFIXES = (
    "docs/",
)
DEFAULT_DOC_PATHS = {
    ".agent-workflows/README.md",
    ".agent-workflows/agent-permission-policy.json",
    ".agent-workflows/area-contracts.json",
    ".agent-workflows/instruction-budgets.json",
    ".agent-workflows/repo-review.md",
    ".github/pull_request_template.md",
    ".github/copilot-instructions.md",
}
EXCLUDED_PREFIXES = (
    ".git/",
    ".doc-contract-kit/updates/",
    ".agent-workflows/runs/",
    ".agent-workflows/tasks/",
    ".venv/",
    "venv/",
    "node_modules/",
    "__pycache__/",
)
FOCUS_TERMS = {
    "docs-impact": [
        "docs-impact",
        "doc-impact",
        "documentation impact",
        "docs check",
        "docs-check",
        "changed files",
        "documentation contract",
    ],
    "impact": [
        "docs-impact",
        "documentation impact",
        "docs-check",
        "documentation contract",
    ],
    "waiver": [
        "waive",
        "waiver",
        "no docs needed",
        "human approval",
        "reason",
        "reviewer",
    ],
    "waive-docs": [
        "waive",
        "waiver",
        "waive-docs",
        "no docs needed",
        "human approval",
    ],
    "docs-propose": [
        "docs-propose",
        "docs patch",
        "proposal",
        "sidecar",
        "missing docs",
        "agent-docs-propose",
    ],
    "add-docs": [
        "add-docs",
        "docs patch",
        "proposal",
        "task packet",
        "write",
    ],
    "slash": [
        "slash command",
        "docs-impact",
        "waive-docs",
        "add-docs",
        "review-docs",
    ],
    "changelog": [
        "changelog",
        "version",
        "release note",
        "agent-changelog-update",
        "update-changelog",
    ],
}
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "by",
    "can",
    "do",
    "does",
    "doc",
    "docs",
    "documentation",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "agent",
    "agents",
    "me",
    "of",
    "or",
    "repo",
    "repository",
    "should",
    "the",
    "to",
    "what",
    "when",
    "work",
    "with",
}


@dataclass(frozen=True)
class Section:
    path: str
    heading: str
    heading_level: int | None
    start_line: int
    end_line: int
    text: str


def io_record(performed: bool, reason: str, paths: list[str] | None = None) -> dict[str, Any]:
    return {
        "performed": performed,
        "paths": paths or [],
        "reason": reason,
    }


def normalize_repo(path: str | Path) -> Path:
    repo = Path(path).expanduser().resolve()
    if not repo.exists():
        raise SystemExit(f"Repository path does not exist: {repo}")
    if not repo.is_dir():
        raise SystemExit(f"Repository path is not a directory: {repo}")
    return repo


def normalize_rel(path: str) -> str:
    value = str(path).strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value.strip("/")


def relative_path(repo: Path, path: Path) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


def normalize_filter(repo: Path, value: str) -> str:
    raw = str(value).strip()
    if not raw:
        return ""
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            return normalize_rel(raw)
    return normalize_rel(raw)


def path_matches_filters(path: str, filters: list[str]) -> bool:
    if not filters:
        return True
    for pattern in filters:
        pattern = normalize_rel(pattern)
        if not pattern:
            continue
        directory_pattern = pattern.rstrip("/") + "/"
        if path == pattern or path.startswith(directory_pattern):
            return True
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def is_excluded(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def is_default_doc_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if "/" not in path and name in ROOT_DOC_FILENAMES:
        return True
    if path in DEFAULT_DOC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in DEFAULT_DOC_PREFIXES)


def is_text_doc(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def discover_doc_paths(repo: Path, path_filters: list[str]) -> list[Path]:
    paths: list[Path] = []
    for path in repo.rglob("*"):
        if not path.is_file() or not is_text_doc(path):
            continue
        rel = relative_path(repo, path)
        if is_excluded(rel):
            continue
        if path_filters:
            if path_matches_filters(rel, path_filters):
                paths.append(path)
        elif is_default_doc_path(rel):
            paths.append(path)
    return sorted(paths, key=lambda item: relative_path(repo, item))


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def split_sections(repo: Path, path: Path) -> list[Section]:
    rel = relative_path(repo, path)
    text = read_text(path)
    lines = text.splitlines()
    if not lines:
        return [
            Section(
                path=rel,
                heading="(empty file)",
                heading_level=None,
                start_line=1,
                end_line=1,
                text="",
            )
        ]

    if path.suffix.lower() not in {".md", ".markdown"}:
        return [
            Section(
                path=rel,
                heading="(whole file)",
                heading_level=None,
                start_line=1,
                end_line=len(lines),
                text="\n".join(lines),
            )
        ]

    sections: list[Section] = []
    current_heading = "(document start)"
    current_level: int | None = None
    current_start = 1
    for index, line in enumerate(lines, start=1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        if index > current_start:
            sections.append(
                Section(
                    path=rel,
                    heading=current_heading,
                    heading_level=current_level,
                    start_line=current_start,
                    end_line=index - 1,
                    text="\n".join(lines[current_start - 1 : index - 1]),
                )
            )
        current_heading = match.group(2).strip()
        current_level = len(match.group(1))
        current_start = index

    sections.append(
        Section(
            path=rel,
            heading=current_heading,
            heading_level=current_level,
            start_line=current_start,
            end_line=len(lines),
            text="\n".join(lines[current_start - 1 :]),
        )
    )
    return sections


def tokenize(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]*", value.lower())
        if len(token) > 1 and token not in STOP_WORDS
    ]


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip().lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def query_terms(question: str, focus: list[str]) -> tuple[list[str], list[str]]:
    phrases = [question]
    expanded = [question]
    for item in focus:
        cleaned = item.strip().lower()
        if not cleaned:
            continue
        expanded.append(cleaned)
        phrases.append(cleaned)
        expanded.extend(FOCUS_TERMS.get(cleaned, []))
        phrases.extend(FOCUS_TERMS.get(cleaned, []))
    tokens = unique_ordered([token for value in expanded for token in tokenize(value)])
    phrase_values = unique_ordered([value for value in phrases if len(value.strip()) > 3])
    return tokens, phrase_values


def count_token(text: str, token: str) -> int:
    return len(re.findall(rf"(?<![a-z0-9_-]){re.escape(token)}(?![a-z0-9_-])", text))


def score_section(section: Section, tokens: list[str], phrases: list[str]) -> tuple[int, list[str]]:
    path_text = section.path.lower()
    heading_text = section.heading.lower()
    body_text = section.text.lower()
    score = 0
    matched: list[str] = []

    for phrase in phrases:
        phrase_score = 0
        if phrase and phrase in path_text:
            phrase_score += 8
        if phrase and phrase in heading_text:
            phrase_score += 10
        if phrase and phrase in body_text:
            phrase_score += 5
        if phrase_score:
            matched.append(phrase)
            score += phrase_score

    for token in tokens:
        token_score = 0
        if count_token(path_text.replace("/", " "), token):
            token_score += 5
        if count_token(heading_text, token):
            token_score += 4
        occurrences = count_token(body_text, token)
        if occurrences:
            token_score += min(occurrences, 4)
        if token_score:
            matched.append(token)
            score += token_score

    if score and section.path == "README.md":
        score += 1
    if score and section.path.startswith("docs/"):
        score += 1
    return score, unique_ordered(matched)


def snippet_for(section: Section, matched_terms: list[str], max_lines: int) -> tuple[str, int, int]:
    raw_lines = section.text.splitlines()
    if not raw_lines:
        return "", section.start_line, section.start_line

    lower_terms = [term.lower() for term in matched_terms if term]
    selected_index = None
    selected_score = 0
    for index, line in enumerate(raw_lines):
        lower_line = line.lower()
        line_score = 0
        for term in lower_terms:
            if term in lower_line:
                line_score += 6 if " " in term or len(term) >= 6 else 1
        if line_score > selected_score:
            selected_score = line_score
            selected_index = index
    if selected_index is None:
        for index, line in enumerate(raw_lines):
            if line.strip():
                selected_index = index
                break
    if selected_index is None:
        selected_index = 0

    start = max(0, selected_index - 1)
    end = min(len(raw_lines), start + max(1, max_lines))
    snippet_lines = [line.rstrip() for line in raw_lines[start:end]]
    while snippet_lines and not snippet_lines[0].strip():
        start += 1
        snippet_lines.pop(0)
    while snippet_lines and not snippet_lines[-1].strip():
        end -= 1
        snippet_lines.pop()
    snippet = "\n".join(snippet_lines)
    if len(snippet) > 700:
        snippet = snippet[:697].rstrip() + "..."
    return snippet, section.start_line + start, max(section.start_line + start, section.start_line + end - 1)


def citation_record(section: Section, score: int, matched_terms: list[str], max_snippet_lines: int) -> dict[str, Any]:
    snippet, line_start, line_end = snippet_for(section, matched_terms, max_snippet_lines)
    return {
        "path": section.path,
        "heading": section.heading,
        "heading_level": section.heading_level,
        "line_start": line_start,
        "line_end": line_end,
        "score": score,
        "matched_terms": matched_terms,
        "snippet": snippet,
    }


def select_citations(
    sections: list[Section],
    *,
    tokens: list[str],
    phrases: list[str],
    max_results: int,
    max_snippet_lines: int,
) -> list[dict[str, Any]]:
    scored: list[tuple[int, Section, list[str]]] = []
    for section in sections:
        score, matched_terms = score_section(section, tokens, phrases)
        if score > 0:
            scored.append((score, section, matched_terms))
    scored.sort(key=lambda item: (-item[0], item[1].path, item[1].start_line, item[1].heading))
    return [
        citation_record(section, score, matched_terms, max_snippet_lines)
        for score, section, matched_terms in scored[: max(1, max_results)]
    ]


def build_local_prompt(question: str, citations: list[dict[str, Any]], result: str) -> str:
    lines = [
        "Use the local repository documentation excerpts below to answer the question.",
        "Do not use hosted models, network search, or uncited policy claims.",
        "If the excerpts do not answer the question, say that no matching local docs were found.",
        "Do not waive documentation work or edit files from this prompt; route write follow-up to docs-impact, docs-propose, /add-docs, or an approved task packet.",
        "",
        f"Question: {question}",
        f"Match result: {result}",
        "",
        "Cited excerpts:",
    ]
    if citations:
        for index, citation in enumerate(citations, start=1):
            lines.extend(
                [
                    f"{index}. {citation['path']} :: {citation['heading']} "
                    f"(lines {citation['line_start']}-{citation['line_end']})",
                    citation["snippet"] or "(no snippet text)",
                    "",
                ]
            )
    else:
        lines.append("- No matching excerpts were found in the scanned local docs.")
    return "\n".join(lines).rstrip() + "\n"


def next_commands(result: str) -> dict[str, list[str]]:
    commands = {
        "read_only": [
            "make agent-docs-explain DOCS_EXPLAIN_QUESTION=\"<question>\"",
            "make agent-docs-localize",
            "make docs-check",
        ],
        "proposal": [
            "make agent-docs-propose",
            "python3 scripts/repo_contract_kit.py docs-propose --repo <repo> --working-tree --json",
        ],
        "human_review": [
            "/waive-docs --reason \"<human reason>\"",
            "/add-docs --path <doc-path> --mode propose",
        ],
    }
    if result != "matched":
        commands["read_only"].insert(1, "retry with DOCS_EXPLAIN_FOCUS=<topic> or DOCS_EXPLAIN_PATH=<path>")
    return commands


def build_report(args: argparse.Namespace, repo: Path | str | None = None) -> tuple[dict[str, Any], int]:
    repo_path = normalize_repo(repo or args.repo)
    question = (getattr(args, "question", None) or DEFAULT_QUESTION).strip()
    focus = [item.strip() for item in (getattr(args, "focus", None) or []) if item and item.strip()]
    path_filters = [
        normalized
        for normalized in (normalize_filter(repo_path, value) for value in (getattr(args, "paths", None) or []))
        if normalized
    ]
    max_results = max(1, int(getattr(args, "max_results", DEFAULT_MAX_RESULTS) or DEFAULT_MAX_RESULTS))
    max_snippet_lines = max(1, int(getattr(args, "max_snippet_lines", DEFAULT_SNIPPET_LINES) or DEFAULT_SNIPPET_LINES))

    doc_paths = discover_doc_paths(repo_path, path_filters)
    sections: list[Section] = []
    for path in doc_paths:
        sections.extend(split_sections(repo_path, path))

    tokens, phrases = query_terms(question, focus)
    citations = select_citations(
        sections,
        tokens=tokens,
        phrases=phrases,
        max_results=max_results,
        max_snippet_lines=max_snippet_lines,
    )
    if citations:
        result = "matched"
        uncertainty = []
    elif doc_paths:
        result = "no-matching-docs"
        uncertainty = [
            "Scanned local docs did not contain matching terms for the question/focus/path filters.",
            "Retry with a different focus or path, or inspect the scanned paths manually before waiving docs work.",
        ]
    else:
        result = "no-docs-found"
        uncertainty = [
            "No local documentation files matched the default docs set or supplied path filters.",
            "Do not infer repo policy from missing docs; ask for a docs patch or task packet when policy is needed.",
        ]

    prompt = build_local_prompt(question, citations, result)
    exit_code = 1 if getattr(args, "check", False) and result != "matched" else 0
    payload = {
        "schema_version": 1,
        "command": "docs-explain",
        "repo": str(repo_path),
        "question": question,
        "focus": focus,
        "path_filters": path_filters,
        "scanned_paths": [relative_path(repo_path, path) for path in doc_paths],
        "scanned_path_count": len(doc_paths),
        "result": result,
        "target_repo_writes": io_record(False, "read-only docs explainer; target files are never written"),
        "sidecar_writes": io_record(False, "non-mutating command; no sidecar artifacts are written by default"),
        "network": {
            "used": False,
            "hosted_model_used": False,
            "reason": "local deterministic file scan only",
        },
        "citations": citations,
        "local_prompt": {
            "purpose": "Ground a docs-policy answer in local source excerpts before waiving docs work or requesting docs patches.",
            "text": prompt,
        },
        "uncertainty": uncertainty,
        "next_commands": next_commands(result),
        "exit_code": exit_code,
    }
    return payload, exit_code


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Docs explainer: {payload['result']}",
        f"Target writes performed: {str(payload['target_repo_writes']['performed']).lower()}",
        f"Sidecar writes performed: {str(payload['sidecar_writes']['performed']).lower()}",
        f"Network/model calls: {str(payload['network']['used']).lower()}",
        "",
        f"Question: {payload['question']}",
    ]
    if payload["focus"]:
        lines.append(f"Focus: {', '.join(payload['focus'])}")
    if payload["path_filters"]:
        lines.append(f"Path filters: {', '.join(payload['path_filters'])}")
    lines.extend(["", "Matched source evidence:"])
    if payload["citations"]:
        for citation in payload["citations"]:
            lines.append(
                f" - {citation['path']} :: {citation['heading']} "
                f"(lines {citation['line_start']}-{citation['line_end']}, score {citation['score']})"
            )
            if citation["snippet"]:
                for snippet_line in citation["snippet"].splitlines():
                    lines.append(f"   {snippet_line}")
    else:
        lines.append(" - none")
        for item in payload["uncertainty"]:
            lines.append(f"   {item}")

    lines.extend(["", "Local prompt:", ""])
    lines.append(payload["local_prompt"]["text"].rstrip())
    lines.extend(["", "Next safe commands:"])
    for command in payload["next_commands"]["read_only"]:
        lines.append(f" - {command}")
    lines.extend(["", "Write follow-up requires explicit scope/review:"])
    for command in payload["next_commands"]["proposal"]:
        lines.append(f" - {command}")
    lines.extend(["", "Human review boundaries:"])
    for command in payload["next_commands"]["human_review"]:
        lines.append(f" - {command}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explain local repository docs with deterministic citations")
    parser.add_argument("--repo", default=".", help="Target repository. Defaults to the current directory.")
    parser.add_argument("--question", "-q", help="Question to ground in local docs.")
    parser.add_argument("--focus", action="append", help="Topic to boost, for example docs-impact, waiver, or add-docs.")
    parser.add_argument("--path", action="append", dest="paths", help="Repo-relative docs path, directory, or glob to scan.")
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS)
    parser.add_argument("--max-snippet-lines", type=int, default=DEFAULT_SNIPPET_LINES)
    parser.add_argument("--check", action="store_true", help="Exit non-zero when no matching docs are found.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload, exit_code = build_report(args)
    if args.json or args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload), end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
