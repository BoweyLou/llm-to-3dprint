#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote

# Script flow:
# 1. Load docs-impact JSON or build a small direct-input payload.
# 2. Normalize categories, changed files, docs files, and missing coverage.
# 3. Render deterministic Markdown for a GitHub PR comment.
# 4. Write to stdout or an output file for a workflow to publish.
#
# Function guide:
# - load_payload/build_direct_payload collect input facts.
# - status_word/policy_link/suggested_doc_links format stable comment content.
# - render_comment builds the Markdown body with policy links and next actions.

COMMENT_MARKER = "<!-- repo-contract-kit:docs-contract-comment -->"

DEFAULT_POLICY_LINKS = [
    ("Documentation contract", "docs/documentation-contract.md"),
    ("Pull request checklist", ".github/pull_request_template.md"),
    ("Agent instructions", "AGENTS.md"),
    ("Agent workflow runbook", "docs/ops/agent-workflow.md"),
]


def unique_sorted(values):
    return sorted({str(value).strip() for value in values if str(value).strip()})


def read_json_path(path: str):
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_payload(path: str):
    payload = read_json_path(path)
    if not isinstance(payload, dict):
        raise SystemExit("docs-impact JSON must be an object")
    return payload


def build_direct_payload(args):
    missing_categories = unique_sorted(args.missing_category or [])
    status = args.status
    if status == "waived":
        status = "pass"
        no_docs_declaration = True
    else:
        no_docs_declaration = bool(args.no_docs_declaration)
    if status is None:
        status = "fail" if missing_categories and not no_docs_declaration else "pass"

    category_names = unique_sorted((args.category or []) + missing_categories)
    categories = [
        {
            "category": category,
            "changed_files": [],
            "suggested_doc_paths": [],
            "covered": category not in missing_categories,
        }
        for category in category_names
    ]
    return {
        "status": status,
        "changed_files": unique_sorted(args.changed_file or []),
        "docs_changed": unique_sorted(args.doc_changed or []),
        "categories": categories,
        "missing_categories": missing_categories,
        "no_docs_declaration": no_docs_declaration,
        "result": "missing-docs" if status == "fail" else "covered-or-no-impact",
    }


def normalize_categories(payload):
    missing = set(unique_sorted(payload.get("missing_categories") or []))
    normalized = []
    for item in payload.get("categories") or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip()
        if not category:
            continue
        covered = bool(item.get("covered"))
        normalized.append(
            {
                "category": category,
                "changed_files": unique_sorted(item.get("changed_files") or []),
                "suggested_doc_paths": unique_sorted(item.get("suggested_doc_paths") or []),
                "covered": covered,
                "missing": category in missing and not covered,
            }
        )
    return sorted(normalized, key=lambda item: item["category"])


def status_word(payload):
    missing = bool(payload.get("missing_categories"))
    no_docs_declaration = bool(payload.get("no_docs_declaration"))
    if payload.get("status") == "fail":
        return "FAIL"
    if missing and no_docs_declaration:
        return "WAIVED"
    return "PASS"


def md_cell(value):
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def repo_blob_link(path, repo_url="", ref=""):
    if not repo_url or not ref:
        return path
    return f"{repo_url.rstrip('/')}/blob/{quote(ref, safe='')}/{quote(path, safe='/._-')}"


def markdown_link(label, path, repo_url="", ref=""):
    return f"[{label}]({repo_blob_link(path, repo_url, ref)})"


def policy_links(repo_url="", ref=""):
    return [f"- {markdown_link(label, path, repo_url, ref)}" for label, path in DEFAULT_POLICY_LINKS]


def suggested_doc_links(paths, repo_url="", ref=""):
    if not paths:
        return "none"
    return ", ".join(markdown_link(path, path, repo_url, ref) for path in paths)


def category_status(category, payload):
    if category["covered"]:
        return "covered"
    if category["missing"] and payload.get("no_docs_declaration"):
        return "waived"
    if category["missing"]:
        return "missing"
    return "not covered"


def category_table(payload, repo_url="", ref=""):
    categories = normalize_categories(payload)
    if not categories:
        return ["No doc-impacting categories were detected."]

    lines = [
        "| Category | Status | Changed files | Suggested docs |",
        "| --- | --- | --- | --- |",
    ]
    for category in categories:
        changed_files = ", ".join(category["changed_files"]) if category["changed_files"] else "none"
        suggested = suggested_doc_links(category["suggested_doc_paths"], repo_url, ref)
        lines.append(
            "| "
            + " | ".join(
                [
                    md_cell(category["category"]),
                    md_cell(category_status(category, payload)),
                    md_cell(changed_files),
                    md_cell(suggested),
                ]
            )
            + " |"
        )
    return lines


def next_actions(payload):
    word = status_word(payload)
    if word == "FAIL":
        return [
            "- Update one of the suggested docs for each missing category.",
            "- Or add `No docs needed: <reason>` to the PR body if the change truly needs no docs.",
            "- Re-run the docs contract after updating docs or the PR body.",
        ]
    if word == "WAIVED":
        return [
            "- Keep the `No docs needed:` reason specific enough for reviewers to audit.",
            "- Add docs before merge if the PR changes public behavior, APIs, CLI, config, schemas, or operations.",
        ]
    if payload.get("categories"):
        return [
            "- Keep changed docs aligned with the behavior, API, CLI, config, or operations change.",
        ]
    return [
        "- No docs-contract action is needed unless this PR changes public behavior, APIs, CLI, config, schemas, or operations.",
    ]


def render_comment(payload, repo_url="", ref="", run_url=""):
    word = status_word(payload)
    changed_files = unique_sorted(payload.get("changed_files") or [])
    docs_changed = unique_sorted(payload.get("docs_changed") or [])
    missing = unique_sorted(payload.get("missing_categories") or [])
    categories = [item["category"] for item in normalize_categories(payload)]

    lines = [
        COMMENT_MARKER,
        "## Documentation Contract Status",
        "",
        f"Status: {word}",
        "",
        "| Check | Result |",
        "| --- | --- |",
        f"| Changed files checked | {len(changed_files)} |",
        f"| Documentation files changed | {len(docs_changed)} |",
        f"| Doc-impact categories | {md_cell(', '.join(categories) if categories else 'none')} |",
        f"| Missing categories | {md_cell(', '.join(missing) if missing else 'none')} |",
        f"| No-docs declaration | {'yes' if payload.get('no_docs_declaration') else 'no'} |",
        "",
        "### Details",
        "",
        *category_table(payload, repo_url, ref),
        "",
        "### Policy Links",
        "",
        *policy_links(repo_url, ref),
        "",
        "### Next Actions",
        "",
        *next_actions(payload),
    ]
    if run_url:
        lines.extend(["", f"Workflow run: {run_url}"])
    return "\n".join(lines).rstrip() + "\n"


def parse_args():
    parser = argparse.ArgumentParser(description="Render a docs-contract PR comment")
    parser.add_argument("--doc-impact-json", help="Path to check_doc_impact.py --format json output, or '-' for stdin.")
    parser.add_argument("--output", help="Write the rendered Markdown comment to this path.")
    parser.add_argument("--repo-url", default="", help="Repository URL used for policy links.")
    parser.add_argument("--ref", default="", help="Git ref or SHA used for policy links.")
    parser.add_argument("--run-url", default="", help="Optional workflow run URL to include in the comment.")
    parser.add_argument("--status", choices=["pass", "fail", "waived"], help="Direct status when JSON is not supplied.")
    parser.add_argument("--changed-file", action="append", help="Direct changed file input. Repeat as needed.")
    parser.add_argument("--doc-changed", action="append", help="Direct changed documentation file input. Repeat as needed.")
    parser.add_argument("--category", action="append", help="Direct doc-impact category input. Repeat as needed.")
    parser.add_argument("--missing-category", action="append", help="Direct missing category input. Repeat as needed.")
    parser.add_argument("--no-docs-declaration", action="store_true", help="Direct no-docs declaration input.")
    return parser.parse_args()


def main():
    args = parse_args()
    payload = load_payload(args.doc_impact_json) if args.doc_impact_json else build_direct_payload(args)
    comment = render_comment(payload, repo_url=args.repo_url, ref=args.ref, run_url=args.run_url)
    if args.output:
        Path(args.output).write_text(comment, encoding="utf-8")
    else:
        sys.stdout.write(comment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
