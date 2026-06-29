#!/usr/bin/env python3

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Script flow:
# 1. Discover agent-facing instruction files from known paths and glob patterns.
# 2. Scan content for hidden characters, placeholders, unsafe guidance, and secret-like values.
# 3. Check referenced commands and paths so instructions do not point at missing assets.
# 4. Emit text or SARIF findings for local and CI usage.
#
# Function guide:
# - normalize_candidate/is_path_like/candidate_path_roots/discover_files choose lint targets.
# - check_hidden_chars/line_has_placeholder/check_secrets_and_unsafe_guidance scan content risks.
# - make_targets/command_lines/check_command_references validate commands.
# - load_budget_config/check_instruction_budget detect context-stuffing risk.
# - check_rule_bloat_and_provenance/check_contradictions detect maintainability problems.
# - referenced_paths/check_referenced_paths validate mentioned files.
# - check_file/issue_dict/sarif_payload/print_issues/parse_args/main run and report linting.

DEFAULT_BUDGET_CONFIG = ".agent-workflows/instruction-budgets.json"

DEFAULT_FILES = [
    "AGENTS.md",
    "REVIEW.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
]

DEFAULT_GLOBS = [
    ".agent-workflows/**/*.md",
    ".codex/prompts/**/*.md",
    ".cursor/rules/**/*",
    ".continue/rules/**/*.md",
    ".windsurf/rules/**/*.md",
]

IGNORED_PATH_PARTS = {
    ".agent-workflows/runs",
}

HIDDEN_CODEPOINTS = {
    "\u200b": "zero width space",
    "\u200c": "zero width non-joiner",
    "\u200d": "zero width joiner",
    "\ufeff": "byte-order mark",
    "\u202a": "left-to-right embedding",
    "\u202b": "right-to-left embedding",
    "\u202c": "pop directional formatting",
    "\u202d": "left-to-right override",
    "\u202e": "right-to-left override",
    "\u2066": "left-to-right isolate",
    "\u2067": "right-to-left isolate",
    "\u2068": "first-strong isolate",
    "\u2069": "pop directional isolate",
}

CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
PATH_LIKE_RE = re.compile(
    r"(^\.?/)|(/)|(\.(md|json|py|ya?ml|toml|txt|ini|cfg|sh)$)|"
    r"^(AGENTS|REVIEW|CLAUDE|GEMINI|Makefile)(\.md)?$"
)

OPTIONAL_AGENT_ADAPTERS = (
    "README.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".cursor/rules/",
    ".continue/rules/",
    ".windsurf/rules/",
)

GENERATED_OUTPUT_EXAMPLES = {
    "session-receipt.json",
}

DEFAULT_BUDGETS = [
    {"pattern": "AGENTS.md", "max_lines": 160, "max_rule_bullets": 40, "severity": "warning"},
    {"pattern": "REVIEW.md", "max_lines": 120, "max_rule_bullets": 32, "severity": "warning"},
    {"pattern": "CLAUDE.md", "max_lines": 140, "max_rule_bullets": 36, "severity": "warning"},
    {"pattern": "GEMINI.md", "max_lines": 140, "max_rule_bullets": 36, "severity": "warning"},
    {
        "pattern": ".github/copilot-instructions.md",
        "max_lines": 120,
        "max_rule_bullets": 32,
        "severity": "warning",
    },
    {"pattern": ".cursor/rules/**", "max_lines": 120, "max_rule_bullets": 32, "severity": "warning"},
    {"pattern": ".continue/rules/**", "max_lines": 120, "max_rule_bullets": 32, "severity": "warning"},
    {"pattern": ".windsurf/rules/**", "max_lines": 120, "max_rule_bullets": 32, "severity": "warning"},
    {
        "pattern": ".agent-workflows/**/*.md",
        "max_lines": 260,
        "max_rule_bullets": 60,
        "severity": "warning",
    },
    {"pattern": ".codex/prompts/**/*.md", "max_lines": 420, "max_rule_bullets": 80, "severity": "warning"},
]


@dataclass
class Issue:
    severity: str
    path: Path
    message: str
    rule_id: str = "agent-docs"


SECRET_PATTERNS = [
    ("secret-token", re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
]

UNSAFE_COMMAND_PATTERNS = [
    ("destructive-rm", re.compile(r"\brm\s+-[^\n]*r[^\n]*f\b|\brm\s+-[^\n]*f[^\n]*r\b")),
    ("git-reset-hard", re.compile(r"\bgit\s+reset\s+--hard\b")),
    ("git-checkout-path", re.compile(r"\bgit\s+checkout\s+--\b")),
    ("git-clean-force", re.compile(r"\bgit\s+clean\s+-[^\n]*[fd][^\n]*\b")),
    ("force-push", re.compile(r"\bgit\s+push\s+--force(?:-with-lease)?\b")),
    ("curl-pipe-shell", re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(sh|bash)\b")),
    ("world-writable", re.compile(r"\bchmod\s+-R\s+777\b")),
]

WILDCARD_PERMISSION_PATTERNS = [
    ("danger-full-access", re.compile(r"\bdanger-full-access\b|--dangerously-skip-permissions")),
    ("unrestricted-tools", re.compile(r"(?i)\b(unrestricted|allow all|all tools|any tool|wildcard)\b.{0,40}\b(tool|permission|network|filesystem|mcp|shell)\b")),
]

ACCOUNT_MUTATION_PATTERNS = [
    ("browser-account-mutation", re.compile(r"(?i)\b(post|like|follow|bookmark|dm|direct message|send message|comment)\b.{0,40}\b(account|browser|social|x\.com|twitter)\b")),
    ("captcha-bypass", re.compile(r"(?i)\b(captcha|2fa|two-factor)\b.{0,30}\b(bypass|avoid|work around)\b")),
]

RULE_WORD_RE = re.compile(r"\b(must|always|never|required|require|should)\b", re.IGNORECASE)
RULE_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
PROVENANCE_WORD_RE = re.compile(r"\b(because|when|if|unless|so that|to prevent|risk|failure|regression|evidence)\b", re.IGNORECASE)
MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?![=])")
MAKE_INCLUDE_RE = re.compile(r"^\s*(?:-?include|sinclude)\s+(.+)$")
COMMAND_BLOCK_RE = re.compile(r"```(?:bash|sh|shell|zsh|text)?\n(.*?)```", re.DOTALL)
COMMAND_LINE_RE = re.compile(r"^\s*(?:[$]\s*)?(make|python3?|uv|npm|pnpm|yarn|git)\b(.+)$")
CONTRADICTION_PAIRS = [
    (
        "git-commit",
        re.compile(r"\b(do not|never|deny|must not)\b.{0,40}\b(commit|git commit)\b", re.IGNORECASE),
        re.compile(r"\b(may|can|should|must|allow)\b.{0,40}\b(commit|git commit)\b", re.IGNORECASE),
    ),
    (
        "git-push",
        re.compile(r"\b(do not|never|deny|must not)\b.{0,40}\b(push|git push)\b", re.IGNORECASE),
        re.compile(r"\b(may|can|should|must|allow)\b.{0,40}\b(push|git push)\b", re.IGNORECASE),
    ),
    (
        "file-edits",
        re.compile(r"\b(do not|never|deny|must not)\b.{0,40}\b(edit|write|modify)\b.{0,20}\b(file|files|repo|repository)\b", re.IGNORECASE),
        re.compile(r"\b(may|can|should|must|allow)\b.{0,40}\b(edit|write|modify)\b.{0,20}\b(file|files|repo|repository)\b", re.IGNORECASE),
    ),
    (
        "network",
        re.compile(r"\b(do not|never|deny|must not)\b.{0,40}\b(network|internet|curl|wget)\b", re.IGNORECASE),
        re.compile(r"\b(may|can|should|must|allow)\b.{0,40}\b(network|internet|curl|wget)\b", re.IGNORECASE),
    ),
]


def normalize_candidate(value: str):
    candidate = value.strip().strip(",:;)(").strip()
    if not candidate:
        return None
    if candidate.startswith(("http://", "https://", "mailto:")):
        return None
    if candidate.startswith(("path/to/", "/path/to/")):
        return None
    if candidate.endswith(":line") or candidate.endswith(":line-number"):
        return None
    if candidate in GENERATED_OUTPUT_EXAMPLES:
        return None
    if candidate in OPTIONAL_AGENT_ADAPTERS:
        return None
    if " " in candidate:
        return None
    if candidate.startswith(("$", "<", "{")):
        return None
    if any(marker in candidate for marker in ("<", ">", "*")):
        return None
    return candidate


def is_path_like(value: str):
    return bool(PATH_LIKE_RE.search(value))


def candidate_path_roots(root: Path, instruction_file: Path):
    roots = [root, instruction_file.parent]
    for prompt_root in (root / ".codex" / "prompts", root / ".agent-workflows"):
        try:
            instruction_file.relative_to(prompt_root)
        except ValueError:
            continue
        roots.append(prompt_root)
    return roots


def discover_files(root: Path, explicit_files: list[str]):
    paths = []
    for value in explicit_files or DEFAULT_FILES:
        path = root / value
        if path.is_file():
            paths.append(path)

    if not explicit_files:
        for pattern in DEFAULT_GLOBS:
            for path in root.glob(pattern):
                rel = str(path.relative_to(root))
                if any(rel == ignored or rel.startswith(f"{ignored}/") for ignored in IGNORED_PATH_PARTS):
                    continue
                if path.is_file():
                    paths.append(path)

    return sorted({path.resolve() for path in paths})


def load_budget_config(root: Path, config_file: str | None):
    path = (root / config_file).resolve() if config_file else root / DEFAULT_BUDGET_CONFIG
    if not path.exists():
        return {"budgets": DEFAULT_BUDGETS}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON config in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid instruction budget config in {path}: top-level value must be an object")

    budgets = payload.get("budgets", DEFAULT_BUDGETS)
    if not isinstance(budgets, list):
        raise SystemExit(f"Invalid instruction budget config in {path}: budgets must be a list")

    normalized = []
    for index, budget in enumerate(budgets, start=1):
        if not isinstance(budget, dict):
            raise SystemExit(f"Invalid instruction budget entry {index} in {path}: entry must be an object")
        pattern = budget.get("pattern")
        severity = budget.get("severity", "warning")
        if not isinstance(pattern, str) or not pattern.strip():
            raise SystemExit(f"Invalid instruction budget entry {index} in {path}: pattern is required")
        if severity not in {"warning", "error"}:
            raise SystemExit(f"Invalid instruction budget entry {index} in {path}: severity must be warning or error")
        normalized.append(
            {
                "pattern": pattern,
                "max_lines": budget.get("max_lines"),
                "max_rule_bullets": budget.get("max_rule_bullets"),
                "severity": severity,
            }
        )
    return {"budgets": normalized}


def matching_budget(root: Path, path: Path, budget_config: dict):
    rel = path.relative_to(root).as_posix()
    for budget in budget_config.get("budgets", []):
        pattern = budget["pattern"]
        if rel == pattern or fnmatch.fnmatch(rel, pattern):
            return budget
    return None


def count_rule_bullets(lines: list[str]):
    return sum(
        1
        for line in lines
        if RULE_BULLET_RE.match(line.strip()) and RULE_WORD_RE.search(line)
    )


def check_instruction_budget(root: Path, path: Path, text: str, budget_config: dict):
    budget = matching_budget(root, path, budget_config)
    if not budget:
        return []

    issues = []
    lines = text.splitlines()
    line_count = len(lines)
    rule_bullets = count_rule_bullets(lines)
    severity = budget["severity"]

    max_lines = budget.get("max_lines")
    if isinstance(max_lines, int) and line_count > max_lines:
        issues.append(
            Issue(
                severity,
                path,
                f"instruction file has {line_count} lines; budget is {max_lines}. Route detail to scoped docs, contracts, or checker output instead of expanding this file",
                "instruction-budget",
            )
        )

    max_rule_bullets = budget.get("max_rule_bullets")
    if isinstance(max_rule_bullets, int) and rule_bullets > max_rule_bullets:
        issues.append(
            Issue(
                severity,
                path,
                f"instruction file has {rule_bullets} rule-like bullets; budget is {max_rule_bullets}. Promote repeatable rules into contracts or scoped policy docs",
                "rule-budget",
            )
        )

    return issues


def check_hidden_chars(path: Path, text: str):
    issues = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for char, name in HIDDEN_CODEPOINTS.items():
            if char in line:
                issues.append(Issue("error", path, f"hidden Unicode {name} at line {line_number}", "hidden-unicode"))
    return issues


def line_has_placeholder(line: str):
    lowered = line.lower()
    return any(value in lowered for value in ("example", "placeholder", "<", ">", "your_", "changeme", "redacted"))


def check_secrets_and_unsafe_guidance(path: Path, text: str):
    issues = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line_has_placeholder(line):
            continue
        for rule_id, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                issues.append(Issue("error", path, f"possible secret or credential at line {line_number}", rule_id))
        for rule_id, pattern in UNSAFE_COMMAND_PATTERNS:
            if pattern.search(line):
                issues.append(Issue("error", path, f"unsafe command guidance at line {line_number}", rule_id))
        for rule_id, pattern in WILDCARD_PERMISSION_PATTERNS:
            if pattern.search(line):
                issues.append(Issue("error", path, f"wildcard or unrestricted permission guidance at line {line_number}", rule_id))
        for rule_id, pattern in ACCOUNT_MUTATION_PATTERNS:
            if "do not" in line.lower() or "deny" in line.lower() or "no " in line.lower():
                continue
            if pattern.search(line):
                issues.append(Issue("error", path, f"unsafe account-mutation guidance at line {line_number}", rule_id))
    return issues


def make_include_paths(root: Path, line: str):
    match = MAKE_INCLUDE_RE.match(line)
    if not match:
        return []

    include_text = match.group(1).split("#", 1)[0].strip()
    if not include_text:
        return []

    paths = []
    for value in include_text.split():
        if "$" in value or "%" in value:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        try:
            path = path.resolve()
            path.relative_to(root.resolve())
        except ValueError:
            continue
        paths.append(path)
    return paths


def make_targets(root: Path):
    targets = set()
    seen = set()

    def collect(makefile: Path):
        try:
            makefile = makefile.resolve()
            makefile.relative_to(root.resolve())
        except ValueError:
            return
        if makefile in seen or not makefile.exists():
            return
        seen.add(makefile)
        try:
            text = makefile.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return
        for line in text.splitlines():
            match = MAKE_TARGET_RE.match(line)
            if match and not match.group(1).startswith("."):
                targets.add(match.group(1))
            for include_path in make_include_paths(root, line):
                collect(include_path)

    collect(root / "Makefile")
    return targets


def command_lines(text: str):
    for block in COMMAND_BLOCK_RE.finditer(text):
        for line in block.group(1).splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                yield stripped
    for value in CODE_SPAN_RE.finditer(text):
        candidate = value.group(1).strip()
        if COMMAND_LINE_RE.match(candidate):
            yield candidate


def check_command_references(root: Path, path: Path, text: str):
    issues = []
    targets = make_targets(root)
    for line in command_lines(text):
        match = COMMAND_LINE_RE.match(line)
        if not match:
            continue
        command, rest = match.group(1), match.group(2).strip()
        parts = rest.split()
        if command == "make":
            explicit_targets = [part for part in parts if "=" not in part and not part.startswith("-")]
            for target in explicit_targets:
                if targets and target not in targets:
                    issues.append(Issue("error", path, f"referenced Make target does not exist: {target}", "stale-command"))
        if command in {"python", "python3"}:
            script = next((part.strip("'\"") for part in parts if part.endswith(".py") and not part.startswith("$")), None)
            if script:
                candidate = (root / script).resolve()
                try:
                    candidate.relative_to(root.resolve())
                except ValueError:
                    continue
                if not candidate.exists():
                    issues.append(Issue("error", path, f"referenced Python script does not exist: {script}", "stale-command"))
    return issues


def check_rule_bloat_and_provenance(path: Path, text: str):
    issues = []
    lines = text.splitlines()
    if len(lines) > 900:
        issues.append(Issue("warning", path, f"instruction file is long ({len(lines)} lines); consider splitting scoped rules", "rule-bloat"))
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if len(stripped) > 260:
            issues.append(Issue("warning", path, f"long instruction line at {line_number}", "rule-bloat"))
        if stripped.startswith(("-", "*")) and RULE_WORD_RE.search(stripped) and not PROVENANCE_WORD_RE.search(stripped):
            issues.append(Issue("warning", path, f"rule-like bullet lacks context/provenance at line {line_number}", "rule-provenance"))
    return issues


def check_contradictions(path: Path, text: str):
    issues = []
    normalized = " ".join(text.split())
    for topic, deny_re, allow_re in CONTRADICTION_PAIRS:
        if deny_re.search(normalized) and allow_re.search(normalized):
            issues.append(
                Issue(
                    "warning",
                    path,
                    f"possible contradictory instruction about {topic}; split by trust profile or approval state",
                    "contradiction",
                )
            )
    return issues


def referenced_paths(text: str):
    values = []
    values.extend(match.group(1) for match in CODE_SPAN_RE.finditer(text))
    values.extend(match.group(1) for match in MARKDOWN_LINK_RE.finditer(text))

    for value in values:
        candidate = normalize_candidate(value)
        if candidate and is_path_like(candidate):
            yield candidate


def check_referenced_paths(root: Path, path: Path, text: str, strict_paths: bool):
    issues = []
    for candidate in referenced_paths(text):
        normalized = candidate.rstrip("/")
        if not normalized:
            continue
        if normalized.startswith("#"):
            continue
        if "://" in normalized:
            continue

        possible_targets = []
        escaped = False
        for base in candidate_path_roots(root, path):
            target = (base / normalized).resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError:
                escaped = True
                continue
            possible_targets.append(target)

        if possible_targets and any(target.exists() for target in possible_targets):
            continue

        if not possible_targets and escaped:
                issues.append(Issue("error", path, f"path reference escapes repo: {candidate}", "path-escape"))
        else:
            severity = "error" if strict_paths else "warning"
            issues.append(Issue(severity, path, f"referenced path does not exist: {candidate}", "missing-path"))
    return issues


def check_file(root: Path, path: Path, strict_paths: bool, budget_config: dict):
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [Issue("error", path, "file is not valid UTF-8")]

    issues = []
    issues.extend(check_hidden_chars(path, text))
    issues.extend(check_referenced_paths(root, path, text, strict_paths))
    issues.extend(check_command_references(root, path, text))
    issues.extend(check_secrets_and_unsafe_guidance(path, text))
    issues.extend(check_contradictions(path, text))
    issues.extend(check_instruction_budget(root, path, text, budget_config))
    issues.extend(check_rule_bloat_and_provenance(path, text))
    return issues


def issue_dict(issue: Issue, root: Path):
    return {
        "severity": issue.severity,
        "rule_id": issue.rule_id,
        "path": str(issue.path.relative_to(root)),
        "message": issue.message,
    }


def sarif_payload(issues: list[Issue], root: Path):
    rules = {}
    results = []
    for issue in issues:
        rules.setdefault(issue.rule_id, {"id": issue.rule_id, "name": issue.rule_id})
        results.append(
            {
                "ruleId": issue.rule_id,
                "level": "error" if issue.severity == "error" else "warning",
                "message": {"text": issue.message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": str(issue.path.relative_to(root))}
                        }
                    }
                ],
            }
        )
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "repo-contract-kit agent instruction linter",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }


def print_issues(issues: list[Issue], root: Path, output_format: str, file_count: int):
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    if output_format == "json":
        print(
            json.dumps(
                {
                    "status": "fail" if errors else "pass",
                    "files_checked": file_count,
                    "error_count": len(errors),
                    "warning_count": len(warnings),
                    "issues": [issue_dict(issue, root) for issue in issues],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    if output_format == "sarif":
        print(json.dumps(sarif_payload(issues, root), indent=2, sort_keys=True))
        return
    for issue in issues:
        rel = issue.path.relative_to(root)
        print(f"{issue.severity.upper()} {rel}: [{issue.rule_id}] {issue.message}")


def parse_args():
    parser = argparse.ArgumentParser(description="Lint local agent instruction files")
    parser.add_argument("--root", default=".", help="Repository root to inspect")
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="Specific instruction file to inspect, relative to root. Repeat as needed.",
    )
    parser.add_argument(
        "--strict-paths",
        action="store_true",
        help="Fail when path-like references do not exist. Without this flag, missing references are warnings.",
    )
    parser.add_argument(
        "--budget-config",
        default=DEFAULT_BUDGET_CONFIG,
        help=f"Instruction budget config relative to root. Defaults to {DEFAULT_BUDGET_CONFIG}.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "sarif"],
        default="text",
        help="Output format for local use or code-scanning adapters.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    files = discover_files(root, args.files)
    budget_config = load_budget_config(root, args.budget_config)

    if not files:
        print("No agent instruction files found.")
        return 0

    all_issues = []
    for path in files:
        all_issues.extend(check_file(root, path, args.strict_paths, budget_config))

    print_issues(all_issues, root, args.format, len(files))

    errors = [issue for issue in all_issues if issue.severity == "error"]
    if errors:
        if args.format == "text":
            print(f"Agent instruction lint failed with {len(errors)} error(s).")
        return 1

    warnings = [issue for issue in all_issues if issue.severity == "warning"]
    if warnings:
        if args.format == "text":
            print(f"Agent instruction lint passed with {len(warnings)} warning(s).")
        return 0

    if args.format == "text":
        print(f"Agent instruction lint passed for {len(files)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
