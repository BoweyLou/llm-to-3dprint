#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_doc_impact import (  # noqa: E402
    CONFIG_FILE,
    evaluate,
    get_staged_changed_files,
    get_unstaged_changed_files,
    get_untracked_files,
    get_changed_files,
    load_config,
    unique_paths,
)

# Script flow:
# 1. Reuse check_doc_impact's change discovery and evaluation logic.
# 2. Convert the evaluation into a local, JSON-friendly impact report.
# 3. Print the report so an agent can decide which docs need attention.
#
# Function guide:
# - changed_files_for_args chooses explicit, staged, working-tree, or branch changes.
# - build_report converts doc-impact evaluation into structured output.
# - parse_args/main drive the CLI wrapper.


def changed_files_for_args(args):
    if args.changed_files:
        return args.changed_files
    if args.staged:
        return get_staged_changed_files()
    if args.working_tree:
        return unique_paths(get_staged_changed_files() + get_unstaged_changed_files() + get_untracked_files())
    return get_changed_files()


def build_report(changed_files, config):
    evaluation = evaluate(changed_files, config)
    categories = []
    for category, files in sorted(evaluation.categories.items()):
        categories.append(
            {
                "category": category,
                "changed_files": sorted(files),
                "suggested_doc_paths": config["category_doc_paths"].get(category, config["doc_paths"]),
                "covered": category in evaluation.covered_categories,
            }
        )

    return {
        "schema_version": 1,
        "changed_files": evaluation.changed_files,
        "docs_changed": evaluation.docs_changed,
        "categories": categories,
        "missing_categories": sorted(evaluation.missing_categories),
        "result": "missing-docs" if evaluation.missing_categories else "covered-or-no-impact",
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Localize likely documentation impact for changed files")
    parser.add_argument("--config", default=CONFIG_FILE, help=f"Path to doc-contract config. Defaults to {CONFIG_FILE}.")
    parser.add_argument(
        "--changed-file",
        action="append",
        dest="changed_files",
        help="Changed file path. Repeat to bypass git detection.",
    )
    parser.add_argument("--staged", action="store_true", help="Inspect staged changes only.")
    parser.add_argument("--working-tree", action="store_true", help="Inspect staged, unstaged, and untracked changes.")
    parser.add_argument("--json", action="store_true", help="Emit JSON. This is the recommended agent interface.")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(args.config)
    changed_files = changed_files_for_args(args)
    report = build_report(changed_files, config)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    if not report["changed_files"]:
        print("No changed files detected.")
        return

    print("Changed files:")
    for path in report["changed_files"]:
        print(f" - {path}")

    if not report["categories"]:
        print("No doc-impacting categories detected.")
        return

    print("Likely documentation impact:")
    for category in report["categories"]:
        print(f" - {category['category']}: {', '.join(category['changed_files'])}")
        print(f"   suggested docs: {', '.join(category['suggested_doc_paths'])}")

    if report["missing_categories"]:
        print(f"Missing documentation coverage for: {', '.join(report['missing_categories'])}")


if __name__ == "__main__":
    main()
