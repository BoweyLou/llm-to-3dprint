MODE ?= bootstrap
BUMP ?= patch
KIT ?=
AGENT ?= manual
AMP ?= amp
RECEIPT ?=
TASK ?=
TITLE ?=
SCOPE ?=
RESEARCH_TITLE ?=
RESEARCH_QUESTION ?=
RESEARCH_CONTEXT ?=
RESEARCH_SOURCES ?= github,arxiv,hacker-news,official-docs
RESEARCH_SOURCE ?= github
RESEARCH_OUTPUT ?= backlog
RESEARCH_QUERY ?=
RESEARCH_SCOPE ?=
BASE_REF ?= HEAD
WORKTREE_ROOT ?=
OVERLAP ?= warn
ALLOW_DIRTY ?= 0
TASK_STATUS_JSON ?= 0
TASK_STATUS_STRICT ?= 0
TASK_STATUS_INCLUDE_CLOSED ?= 0
TASK_CLEANUP_JSON ?= 0
TASK_CLEANUP_APPLY ?= 0
TASK_CLEANUP_MOVE_NESTED ?= 0
TASK_CLEANUP_PRUNE ?= 0

.PHONY: help workflow-help docs-lint docs-build docs-generate docs-check agent-start agent-task-prepare agent-task-status agent-task-cleanup agent-run-review agent-research-plan agent-research-run agent-research-synthesize agent-research-to-task-packet agent-receipt-verify agent-docs-lint agent-docs-localize agent-review agent-learn agent-review-risk agent-task-packet agent-test-first agent-verify kit-status kit-explain kit-update kit-refresh version-status version-check version-bump

help: workflow-help

workflow-help:
	@printf "%s\n" \
		"repo-contract-kit working rhythm" \
		"" \
		"1. Orient" \
		"   make agent-start" \
		"   make kit-status" \
		"2. Review" \
		"   make agent-run-review AGENT=manual" \
		"3. Scope" \
		"   make agent-task-packet" \
		"4. Execute" \
		"   make agent-task-status" \
		"   make agent-task-prepare TASK=<id> SCOPE=<paths>" \
		"   make agent-task-cleanup" \
		"   make agent-verify" \
		"" \
		"Read docs/working-rhythm.md for common paths and the mental model." \
		"Run make kit-explain for installed-kit vs target-repo ownership."

docs-lint:
	@echo "Running basic docs lint checks..."
	@test -f AGENTS.md || (echo "Missing AGENTS.md" && exit 1)
	@test -f REVIEW.md || (echo "Missing REVIEW.md" && exit 1)
	@test -f docs/documentation-contract.md || (echo "Missing docs/documentation-contract.md" && exit 1)
	@test -d docs/adr || (echo "Missing docs/adr/" && exit 1)
	@echo "Basic docs lint checks passed."

docs-build:
	@echo "No docs site configured yet. Skipping build."

docs-generate:
	@echo "No generated docs configured yet. Skipping generation."

docs-check: docs-lint docs-build docs-generate
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_doc_impact.py

agent-start:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_start.py --mode "$(MODE)"

agent-task-prepare:
	@test -n "$(TASK)" || (echo "Set TASK=<id>"; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_prepare.py \
		--task "$(TASK)" \
		--title "$(TITLE)" \
		--scope "$(SCOPE)" \
		--mode "$(MODE)" \
		--base-ref "$(BASE_REF)" \
		--worktree-root "$(WORKTREE_ROOT)" \
		--overlap-policy "$(OVERLAP)" \
		$(if $(filter 1 true yes,$(ALLOW_DIRTY)),--allow-dirty,)

agent-task-status:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_status.py \
		$(if $(filter 1 true yes,$(TASK_STATUS_JSON)),--json,) \
		$(if $(filter 1 true yes,$(TASK_STATUS_STRICT)),--strict,) \
		$(if $(filter 1 true yes,$(TASK_STATUS_INCLUDE_CLOSED)),--include-closed,)

agent-task-cleanup:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_cleanup.py \
		$(if $(filter 1 true yes,$(TASK_CLEANUP_JSON)),--json,) \
		$(if $(filter 1 true yes,$(TASK_CLEANUP_APPLY)),--apply,) \
		$(if $(filter 1 true yes,$(TASK_CLEANUP_MOVE_NESTED)),--move-nested,) \
		$(if $(filter 1 true yes,$(TASK_CLEANUP_PRUNE)),--prune,)

agent-run-review:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_review_run.py --mode "$(MODE)" --agent "$(AGENT)" --amp-command "$(AMP)"

agent-research-plan:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_research.py plan \
		--title "$(RESEARCH_TITLE)" \
		--question "$(RESEARCH_QUESTION)" \
		--context "$(RESEARCH_CONTEXT)" \
		--sources "$(RESEARCH_SOURCES)" \
		--output "$(RESEARCH_OUTPUT)" \
		--query "$(RESEARCH_QUERY)" \
		--scope "$(RESEARCH_SCOPE)"

agent-research-run:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_research.py run \
		--source "$(RESEARCH_SOURCE)" \
		--query "$(RESEARCH_QUERY)" \
		--scope "$(RESEARCH_SCOPE)"

agent-research-synthesize:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_research.py synthesize

agent-research-to-task-packet:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_research.py to-task-packet

agent-receipt-verify:
	@if test -n "$(RECEIPT)"; then \
		PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_agent_receipt.py --strict --receipt "$(RECEIPT)"; \
	else \
		PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_agent_receipt.py --strict; \
	fi

kit-status:
	@if test -n "$(KIT)"; then \
		PYTHONDONTWRITEBYTECODE=1 python3 scripts/kit_status.py --kit "$(KIT)"; \
	else \
		PYTHONDONTWRITEBYTECODE=1 python3 scripts/kit_status.py; \
	fi

kit-explain:
	@if test -n "$(KIT)"; then \
		PYTHONDONTWRITEBYTECODE=1 python3 scripts/kit_status.py --explain --kit "$(KIT)"; \
	else \
		PYTHONDONTWRITEBYTECODE=1 python3 scripts/kit_status.py --explain; \
	fi

kit-update:
	@test -n "$(KIT)" || (echo "Set KIT=/path/to/repo-contract-kit"; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(KIT)/scripts/update.py" "$(CURDIR)" --apply

kit-refresh:
	@test -n "$(KIT)" || (echo "Set KIT=/path/to/repo-contract-kit"; exit 1)
	@git -C "$(KIT)" rev-parse --is-inside-work-tree >/dev/null 2>&1 || (echo "KIT is not a git checkout: $(KIT)"; exit 1)
	@test -f "$(KIT)/scripts/update.py" || (echo "KIT does not look like repo-contract-kit: $(KIT)"; exit 1)
	@test -z "$$(git -C "$(KIT)" status --porcelain)" || (echo "Kit checkout has local changes; commit, stash, or use kit-update explicitly: $(KIT)"; exit 1)
	@git -C "$(KIT)" pull --ff-only
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/kit_status.py --kit "$(KIT)"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(KIT)/scripts/update.py" "$(CURDIR)" --apply

version-status:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/version.py status

version-check:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/version.py check

version-bump:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/version.py bump --bump "$(BUMP)"

agent-docs-lint:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/lint_agent_docs.py --strict-paths

agent-docs-localize:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/localize_doc_impact.py --working-tree --json

agent-review:
	@if test -f .agent-workflows/repo-review.md; then \
		printf "%s\n" \
			"Read AGENTS.md, REVIEW.md, and .agent-workflows/README.md." \
			"Then follow .agent-workflows/repo-review.md in bootstrap mode." \
			"Use the installed personas and prompts under .codex/prompts/ where useful." \
			"Start by running make agent-verify and make agent-docs-localize." \
			"Optionally run make agent-run-review AGENT=manual to generate review artifacts." \
			"Produce a findings backlog before editing code."; \
	elif test -f .codex/prompts/multi-agent-repo-review.md; then \
		printf "%s\n" \
			"Read AGENTS.md and REVIEW.md." \
			"Then follow .codex/prompts/multi-agent-repo-review.md in bootstrap mode." \
			"Start by running make agent-verify and make agent-docs-localize." \
			"Optionally run make agent-run-review AGENT=manual to generate review artifacts." \
			"Produce a findings backlog before editing code."; \
	else \
		echo "Missing local review workflow; install the local-agentic or review-prompts profile."; exit 1; \
	fi

agent-learn:
	@test -f .codex/prompts/codebase-learning-comments.md || (echo "Missing .codex/prompts/codebase-learning-comments.md; install the review-prompts profile." && exit 1)
	@echo "Use .codex/prompts/codebase-learning-comments.md for learner-focused comments."

agent-review-risk:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/classify_review_risk.py --working-tree

agent-task-packet:
	@test -f .codex/prompts/task-packet.md || (echo "Missing .codex/prompts/task-packet.md; install the review-prompts profile." && exit 1)
	@echo "Use .codex/prompts/task-packet.md to convert a backlog item, issue, accepted finding, or human request into executable agent work."

agent-test-first:
	@test -f .codex/prompts/tdd/README.md || (echo "Missing .codex/prompts/tdd/README.md; install the test-first profile." && exit 1)
	@echo "Use .codex/prompts/tdd/README.md to pick the executable-spec prompt."

agent-verify: docs-check agent-docs-lint
	@echo "Agent verification checks passed."
