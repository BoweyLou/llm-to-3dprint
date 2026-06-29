MODE ?= bootstrap
BUMP ?= patch
KIT ?=
WORKFLOW ?=
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
DIRTY_PRIMARY_BASELINE ?= 0
TASK_PREPARE_JSON ?= 0
TASK_STATUS_JSON ?= 0
TASK_STATUS_STRICT ?= 0
TASK_STATUS_INCLUDE_CLOSED ?= 0
STATE_LEDGER_JSON ?= 0
BRANCH_READY_JSON ?= 0
BRANCH_READY_BASE_REF ?=
BRANCH_READY_HEAD_REF ?= HEAD
BRANCH_READY_TARGET_REF ?=
BRANCH_READY_CHECKS_JSON ?=
BRANCH_READY_RECEIPT ?=
BRANCH_READY_REVIEW_DISPOSITION_JSON ?=
BRANCH_READY_NO_DOCS_NEEDED ?=
BRANCH_READY_TASK_RECEIPT ?=
PREFLIGHT_JSON ?= 0
PREFLIGHT_STRICT ?= 0
PREFLIGHT_WRITE_SIDECAR ?= 0
SELF_HEAL_JSON ?= 0
SELF_HEAL_APPLY ?= 0
SELF_HEAL_ALLOW_PATHS ?=
TASK_READY_JSON ?= 0
TASK_READY_RECEIPT ?=
AUTOMATION_HANDOFF_JSON ?= 0
AUTOMATION_HANDOFF_MODE ?= patch
AUTOMATION_HANDOFF_LABEL ?=
AUTOMATION_HANDOFF_ORIGINAL_ROOT ?=
AUTOMATION_HANDOFF_ORIGINAL_BASELINE ?=
AUTOMATION_HANDOFF_CAPTURE_ORIGINAL_BASELINE ?= 0
AUTOMATION_HANDOFF_ALLOW_PRIMARY ?= 0
AUTOMATION_HANDOFF_ALLOW_DIRTY_ORIGINAL ?= 0
AUTOMATION_HANDOFF_ALLOW_ORIGINAL_DRIFT ?= 0
AUTOMATION_HANDOFF_DRY_RUN ?= 0
TASK_CLEANUP_JSON ?= 0
TASK_CLEANUP_APPLY ?= 0
TASK_CLEANUP_MOVE_NESTED ?= 0
TASK_CLEANUP_PRUNE ?= 0
TASK_CLOSEOUT_JSON ?= 0
TASK_CLOSEOUT_APPLY ?= 0
TASK_CLOSEOUT_PRUNE ?= 0
TASK_CLOSEOUT_KEEP ?=
TASK_CLOSEOUT_OLDER_THAN_DAYS ?=
TASK_CLOSEOUT_ALLOW_NO_RECEIPT ?= 0
BACKLOG_ID ?=
BACKLOG_JSON ?= 0
CONTEXT_BUNDLE_JSON ?= 0
CONTEXT_BUNDLE_MODE ?= working-tree
CONTEXT_BUNDLE_MAX_FILES ?= 25
TASK_LIFECYCLE_JSON ?= 0
TASK_LIFECYCLE_APPLY ?= 0
TASK_FINALIZE_ACTION ?= finish
TASK_FINALIZE_JSON ?= 0
TASK_FINALIZE_SKIP_READY ?= 0
TASK_FINALIZE_CLOSEOUT_APPLY ?= 0
TASK_OWNER ?=
TASK_OWNER_LABEL ?=
TASK_SESSION_ID ?=
TASK_THREAD_ID ?=
TASK_AUTOMATION_ID ?=
TASK_REASON ?=
TASK_RECEIPT ?=
TASK_LEASE_MINUTES ?= 240
DOCS_FRESHNESS_JSON ?= 0
DOCS_REQUIRE_SEMANTIC ?= 0
DOCS_SEMANTIC_RECEIPT ?=
DOCS_AS_TESTS_JSON ?= 0
DOCS_AS_TESTS_CONFIG ?= .agent-workflows/docs-as-tests.json
DOCS_EXPLAIN_JSON ?= 0
DOCS_EXPLAIN_CHECK ?= 0
DOCS_EXPLAIN_QUESTION ?=
DOCS_EXPLAIN_FOCUS ?=
DOCS_EXPLAIN_PATH ?=
DOCS_PROPOSE_JSON ?= 0
DOCS_PROPOSE_WRITE_SIDECAR ?= 1
CHANGELOG_UPDATE_JSON ?= 0
CHANGELOG_UPDATE_CHECK ?= 0
CHANGELOG_UPDATE_BUMP ?=
CHANGELOG_UPDATE_VERSION ?=
CHANGELOG_UPDATE_SECTION ?=
CHANGELOG_UPDATE_SUMMARY ?=
GOAL_CHECK_JSON ?= 0
GOAL_CHECK_MODE ?= working-tree
GOAL_CHECK_CONFIG ?= .agent-workflows/area-contracts.json
TOKEN_BUDGET_JSON ?= 0
TOKEN_BUDGET_STRICT ?= 0
INSTRUCTION_DIET_JSON ?= 0
INSTRUCTION_DIET_STRICT_PATHS ?= 1
STACK_UPDATE_JSON ?= 0
STACK_UPDATE_FORCE_MANAGED ?= 0
STACK_UPDATE_COMPAT ?= 0
RUNTIME_ADAPTERS ?=

.PHONY: help workflow-help docs-lint docs-build docs-generate docs-freshness docs-as-tests docs-check goal-check backlog-status backlog-check agent-next agent-context-bundle agent-state-ledger agent-branch-readiness agent-preflight agent-doctor agent-self-heal agent-start agent-task-prepare agent-task-ready agent-automation-handoff agent-task-status agent-task-cleanup agent-task-closeout agent-task-finalize agent-task-finish agent-task-block agent-task-abandon agent-task-heartbeat agent-task-link-receipt agent-task-prune agent-task-packet-from-backlog agent-run-review agent-research-plan agent-research-run agent-research-synthesize agent-research-to-task-packet agent-receipt-verify agent-docs-lint agent-instruction-diet agent-docs-localize agent-docs-explain agent-docs-propose agent-changelog-update agent-token-budget agent-review agent-learn agent-review-risk agent-task-packet agent-test-first agent-verify kit-status kit-explain kit-migrate-config kit-update kit-refresh kit-update-stack kit-refresh-stack version-status version-check version-bump

help: workflow-help

workflow-help:
	@printf "%s\n" \
		"kit working rhythm" \
		"" \
		"1. Orient" \
		"   make agent-start" \
		"   make goal-check" \
		"   make kit-status" \
		"   make agent-next" \
		"   make agent-context-bundle" \
		"   make agent-state-ledger" \
		"   make agent-branch-readiness" \
		"   make agent-preflight" \
		"2. Review" \
		"   make agent-run-review AGENT=manual" \
		"3. Scope" \
		"   make agent-task-packet" \
		"   make agent-task-packet-from-backlog BACKLOG_ID=<id>" \
		"4. Execute" \
		"   make agent-task-status" \
		"   make agent-task-prepare TASK=<id> SCOPE=<paths>" \
		"   make agent-task-ready" \
		"   make agent-automation-handoff" \
		"   make agent-task-heartbeat TASK=<id>" \
		"   make agent-task-finalize TASK=<id> TASK_RECEIPT=<path>" \
		"   make agent-task-finish TASK=<id> TASK_RECEIPT=<path>" \
		"   make agent-task-cleanup" \
		"   make agent-task-closeout" \
		"   make agent-self-heal" \
		"   make docs-as-tests" \
		"   make agent-instruction-diet" \
		"   make agent-docs-explain" \
		"   make agent-docs-propose" \
		"   make agent-changelog-update" \
		"   make agent-token-budget" \
		"   make agent-verify" \
		"   kit status" \
		"   kit update --dry-run" \
		"   kit update" \
		"   kit doctor" \
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

docs-freshness:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_docs_freshness.py \
		$(if $(filter 1 true yes,$(DOCS_FRESHNESS_JSON)),--json,) \
		$(if $(filter 1 true yes,$(DOCS_REQUIRE_SEMANTIC)),--require-semantic-receipt,) \
		$(if $(DOCS_SEMANTIC_RECEIPT),--semantic-receipt "$(DOCS_SEMANTIC_RECEIPT)",)

docs-as-tests:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_docs_as_tests.py \
		--repo "$(CURDIR)" \
		--config "$(DOCS_AS_TESTS_CONFIG)" \
		$(if $(filter 1 true yes,$(DOCS_AS_TESTS_JSON)),--json,)

docs-check: docs-lint docs-build docs-generate docs-freshness
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_doc_impact.py

goal-check:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py goal-check --repo "$(CURDIR)" \
		--config "$(GOAL_CHECK_CONFIG)" \
		$(if $(filter staged,$(GOAL_CHECK_MODE)),--staged,) \
		$(if $(filter working-tree,$(GOAL_CHECK_MODE)),--working-tree,) \
		$(if $(filter 1 true yes,$(GOAL_CHECK_JSON)),--json,)

backlog-status:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py backlog-status --repo "$(CURDIR)" \
		$(if $(filter 1 true yes,$(BACKLOG_JSON)),--json,)

backlog-check:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py backlog-check --repo "$(CURDIR)" \
		$(if $(filter 1 true yes,$(BACKLOG_JSON)),--json,)

agent-next:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py agent-next --repo "$(CURDIR)" \
		$(if $(filter 1 true yes,$(BACKLOG_JSON)),--json,)

agent-context-bundle:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py agent-context-bundle --repo "$(CURDIR)" \
		--mode "$(CONTEXT_BUNDLE_MODE)" \
		--max-files "$(CONTEXT_BUNDLE_MAX_FILES)" \
		$(if $(filter 1 true yes,$(CONTEXT_BUNDLE_JSON)),--json,)

agent-state-ledger:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py agent-state-ledger --repo "$(CURDIR)" \
		$(if $(filter 1 true yes,$(STATE_LEDGER_JSON)),--json,)

agent-branch-readiness:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py branch-readiness --repo "$(CURDIR)" \
		$(if $(BRANCH_READY_BASE_REF),--base-ref "$(BRANCH_READY_BASE_REF)",) \
		$(if $(BRANCH_READY_HEAD_REF),--head-ref "$(BRANCH_READY_HEAD_REF)",) \
		$(if $(BRANCH_READY_TARGET_REF),--target-ref "$(BRANCH_READY_TARGET_REF)",) \
		$(if $(BRANCH_READY_CHECKS_JSON),--checks-json "$(BRANCH_READY_CHECKS_JSON)",) \
		$(if $(BRANCH_READY_RECEIPT),--receipt "$(BRANCH_READY_RECEIPT)",) \
		$(if $(BRANCH_READY_REVIEW_DISPOSITION_JSON),--review-disposition-json "$(BRANCH_READY_REVIEW_DISPOSITION_JSON)",) \
		$(if $(BRANCH_READY_NO_DOCS_NEEDED),--no-docs-needed "$(BRANCH_READY_NO_DOCS_NEEDED)",) \
		$(if $(TASK),--task "$(TASK)",) \
		$(if $(BRANCH_READY_TASK_RECEIPT),--task-receipt "$(BRANCH_READY_TASK_RECEIPT)",) \
		$(if $(filter 1 true yes,$(BRANCH_READY_JSON)),--json,)

agent-preflight:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py agent-preflight --repo "$(CURDIR)" \
		$(if $(filter 1 true yes,$(PREFLIGHT_JSON)),--json,) \
		$(if $(filter 1 true yes,$(PREFLIGHT_STRICT)),--strict,) \
		$(if $(filter 1 true yes,$(PREFLIGHT_WRITE_SIDECAR)),--write-sidecar,)

agent-doctor:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py agent-doctor --repo "$(CURDIR)" \
		$(if $(filter 1 true yes,$(PREFLIGHT_JSON)),--json,) \
		$(if $(filter 1 true yes,$(PREFLIGHT_STRICT)),--strict,) \
		$(if $(filter 1 true yes,$(PREFLIGHT_WRITE_SIDECAR)),--write-sidecar,)

agent-self-heal:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py agent-self-heal --repo "$(CURDIR)" \
		$(if $(filter 1 true yes,$(SELF_HEAL_JSON)),--json,) \
		$(if $(filter 1 true yes,$(SELF_HEAL_APPLY)),--apply,) \
		$(if $(SELF_HEAL_ALLOW_PATHS),--allow-path "$(SELF_HEAL_ALLOW_PATHS)",)

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
		--owner "$(TASK_OWNER)" \
		--owner-label "$(TASK_OWNER_LABEL)" \
		--session-id "$(TASK_SESSION_ID)" \
		--thread-id "$(TASK_THREAD_ID)" \
		--automation-id "$(TASK_AUTOMATION_ID)" \
		--lease-minutes "$(TASK_LEASE_MINUTES)" \
		$(if $(filter 1 true yes,$(TASK_PREPARE_JSON)),--json,) \
		$(if $(filter 1 true yes,$(DIRTY_PRIMARY_BASELINE)),--dirty-primary-baseline,) \
		$(if $(filter 1 true yes,$(ALLOW_DIRTY)),--dirty-primary-baseline,)

agent-task-status:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_status.py \
		$(if $(filter 1 true yes,$(TASK_STATUS_JSON)),--json,) \
		$(if $(filter 1 true yes,$(TASK_STATUS_STRICT)),--strict,) \
		$(if $(filter 1 true yes,$(TASK_STATUS_INCLUDE_CLOSED)),--include-closed,)

agent-task-ready:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_ready.py \
		$(if $(TASK),--task "$(TASK)",) \
		$(if $(BASE_REF),--base-ref "$(BASE_REF)",) \
		$(if $(TASK_READY_RECEIPT),--receipt "$(TASK_READY_RECEIPT)",) \
		$(if $(filter 1 true yes,$(TASK_READY_JSON)),--json,)

agent-automation-handoff:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py automation-handoff \
		--repo "$(CURDIR)" \
		--mode "$(AUTOMATION_HANDOFF_MODE)" \
		$(if $(AUTOMATION_HANDOFF_LABEL),--label "$(AUTOMATION_HANDOFF_LABEL)",) \
		$(if $(AUTOMATION_HANDOFF_ORIGINAL_ROOT),--original-root "$(AUTOMATION_HANDOFF_ORIGINAL_ROOT)",) \
		$(if $(AUTOMATION_HANDOFF_ORIGINAL_BASELINE),--original-baseline "$(AUTOMATION_HANDOFF_ORIGINAL_BASELINE)",) \
		$(if $(filter 1 true yes,$(AUTOMATION_HANDOFF_CAPTURE_ORIGINAL_BASELINE)),--capture-original-baseline,) \
		$(if $(filter 1 true yes,$(AUTOMATION_HANDOFF_ALLOW_PRIMARY)),--allow-primary-checkout,) \
		$(if $(filter 1 true yes,$(AUTOMATION_HANDOFF_ALLOW_DIRTY_ORIGINAL)),--allow-dirty-original,) \
		$(if $(filter 1 true yes,$(AUTOMATION_HANDOFF_ALLOW_ORIGINAL_DRIFT)),--allow-original-baseline-drift,) \
		$(if $(filter 1 true yes,$(AUTOMATION_HANDOFF_DRY_RUN)),--dry-run,) \
		$(if $(filter 1 true yes,$(AUTOMATION_HANDOFF_JSON)),--json,)

agent-task-cleanup:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_cleanup.py \
		$(if $(filter 1 true yes,$(TASK_CLEANUP_JSON)),--json,) \
		$(if $(filter 1 true yes,$(TASK_CLEANUP_APPLY)),--apply,) \
		$(if $(filter 1 true yes,$(TASK_CLEANUP_MOVE_NESTED)),--move-nested,) \
		$(if $(filter 1 true yes,$(TASK_CLEANUP_PRUNE)),--prune,)

agent-task-closeout:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_cleanup.py --closeout \
		$(if $(filter 1 true yes,$(TASK_CLOSEOUT_JSON)),--json,) \
		$(if $(filter 1 true yes,$(TASK_CLOSEOUT_APPLY)),--apply,) \
		$(if $(filter 1 true yes,$(TASK_CLOSEOUT_PRUNE)),--prune,) \
		$(if $(TASK_CLOSEOUT_KEEP),--keep-count "$(TASK_CLOSEOUT_KEEP)",) \
		$(if $(TASK_CLOSEOUT_OLDER_THAN_DAYS),--older-than-days "$(TASK_CLOSEOUT_OLDER_THAN_DAYS)",) \
		$(if $(filter 1 true yes,$(TASK_CLOSEOUT_ALLOW_NO_RECEIPT)),--allow-no-receipt,)

agent-task-finalize:
	@test -n "$(TASK)" || (echo "Set TASK=<id>"; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_finalize.py \
		--task "$(TASK)" \
		--action "$(TASK_FINALIZE_ACTION)" \
		$(if $(TASK_RECEIPT),--receipt "$(TASK_RECEIPT)",) \
		$(if $(BASE_REF),--base-ref "$(BASE_REF)",) \
		$(if $(TASK_REASON),--reason "$(TASK_REASON)",) \
		$(if $(TASK_OWNER),--owner "$(TASK_OWNER)",) \
		$(if $(TASK_OWNER_LABEL),--owner-label "$(TASK_OWNER_LABEL)",) \
		$(if $(TASK_SESSION_ID),--session-id "$(TASK_SESSION_ID)",) \
		$(if $(TASK_THREAD_ID),--thread-id "$(TASK_THREAD_ID)",) \
		$(if $(TASK_AUTOMATION_ID),--automation-id "$(TASK_AUTOMATION_ID)",) \
		$(if $(filter 1 true yes,$(TASK_FINALIZE_JSON)),--json,) \
		$(if $(filter 1 true yes,$(TASK_FINALIZE_SKIP_READY)),--skip-ready,) \
		$(if $(filter 1 true yes,$(TASK_FINALIZE_CLOSEOUT_APPLY)),--closeout-apply,)

agent-task-finish:
	@test -n "$(TASK)" || (echo "Set TASK=<id>"; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_lifecycle.py finish --task "$(TASK)" \
		--reason "$(TASK_REASON)" --receipt "$(TASK_RECEIPT)" --owner "$(TASK_OWNER)" --owner-label "$(TASK_OWNER_LABEL)" --session-id "$(TASK_SESSION_ID)" --thread-id "$(TASK_THREAD_ID)" --automation-id "$(TASK_AUTOMATION_ID)" \
		$(if $(filter 1 true yes,$(TASK_LIFECYCLE_JSON)),--json,)

agent-task-block:
	@test -n "$(TASK)" || (echo "Set TASK=<id>"; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_lifecycle.py block --task "$(TASK)" \
		--reason "$(TASK_REASON)" --owner "$(TASK_OWNER)" --owner-label "$(TASK_OWNER_LABEL)" --session-id "$(TASK_SESSION_ID)" --thread-id "$(TASK_THREAD_ID)" --automation-id "$(TASK_AUTOMATION_ID)" \
		$(if $(filter 1 true yes,$(TASK_LIFECYCLE_JSON)),--json,)

agent-task-abandon:
	@test -n "$(TASK)" || (echo "Set TASK=<id>"; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_lifecycle.py abandon --task "$(TASK)" \
		--reason "$(TASK_REASON)" --owner "$(TASK_OWNER)" --owner-label "$(TASK_OWNER_LABEL)" --session-id "$(TASK_SESSION_ID)" --thread-id "$(TASK_THREAD_ID)" --automation-id "$(TASK_AUTOMATION_ID)" \
		$(if $(filter 1 true yes,$(TASK_LIFECYCLE_JSON)),--json,)

agent-task-heartbeat:
	@test -n "$(TASK)" || (echo "Set TASK=<id>"; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_lifecycle.py heartbeat --task "$(TASK)" \
		--reason "$(TASK_REASON)" --owner "$(TASK_OWNER)" --owner-label "$(TASK_OWNER_LABEL)" --session-id "$(TASK_SESSION_ID)" --thread-id "$(TASK_THREAD_ID)" --automation-id "$(TASK_AUTOMATION_ID)" \
		--lease-minutes "$(TASK_LEASE_MINUTES)" \
		$(if $(filter 1 true yes,$(TASK_LIFECYCLE_JSON)),--json,)

agent-task-link-receipt:
	@test -n "$(TASK)" || (echo "Set TASK=<id>"; exit 1)
	@test -n "$(TASK_RECEIPT)" || (echo "Set TASK_RECEIPT=<path>"; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_lifecycle.py link-receipt --task "$(TASK)" \
		--receipt "$(TASK_RECEIPT)" --reason "$(TASK_REASON)" --owner "$(TASK_OWNER)" --owner-label "$(TASK_OWNER_LABEL)" --session-id "$(TASK_SESSION_ID)" --thread-id "$(TASK_THREAD_ID)" --automation-id "$(TASK_AUTOMATION_ID)" \
		$(if $(filter 1 true yes,$(TASK_LIFECYCLE_JSON)),--json,)

agent-task-prune:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/agent_task_lifecycle.py prune \
		$(if $(filter 1 true yes,$(TASK_LIFECYCLE_APPLY)),--apply,) \
		$(if $(filter 1 true yes,$(TASK_LIFECYCLE_JSON)),--json,)

agent-task-packet-from-backlog:
	@test -n "$(BACKLOG_ID)" || (echo "Set BACKLOG_ID=<id>"; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py agent-task-packet-from-backlog \
		--repo "$(CURDIR)" \
		--backlog-id "$(BACKLOG_ID)" \
		--mode "$(MODE)" \
		$(if $(filter 1 true yes,$(BACKLOG_JSON)),--json,)

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

kit-migrate-config:
	@test -n "$(KIT)" || (echo "Set KIT=/path/to/kit"; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(KIT)/scripts/update.py" "$(CURDIR)" --apply --metadata-only

kit-update:
	@test -n "$(KIT)" || (echo "Set KIT=/path/to/kit"; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(KIT)/scripts/update.py" "$(CURDIR)" --apply \
		$(if $(RUNTIME_ADAPTERS),--runtime-adapters "$(RUNTIME_ADAPTERS)",)

kit-refresh:
	@test -n "$(KIT)" || (echo "Set KIT=/path/to/kit"; exit 1)
	@git -C "$(KIT)" rev-parse --is-inside-work-tree >/dev/null 2>&1 || (echo "KIT is not a git checkout: $(KIT)"; exit 1)
	@test -f "$(KIT)/scripts/update.py" || (echo "KIT does not look like repo-contract-kit: $(KIT)"; exit 1)
	@test -z "$$(git -C "$(KIT)" status --porcelain)" || (echo "Kit checkout has local changes; commit, stash, or use kit-update explicitly: $(KIT)"; exit 1)
	@git -C "$(KIT)" pull --ff-only
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/kit_status.py --kit "$(KIT)"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(KIT)/scripts/update.py" "$(CURDIR)" --apply \
		$(if $(RUNTIME_ADAPTERS),--runtime-adapters "$(RUNTIME_ADAPTERS)",)

kit-update-stack:
	@if test "$(STACK_UPDATE_COMPAT)" != "1" -a "$(STACK_UPDATE_COMPAT)" != "true" -a "$(STACK_UPDATE_COMPAT)" != "yes"; then \
		echo "kit-update-stack is a deprecated maintainer compatibility target."; \
		echo "Ordinary target repos should use: kit update --dry-run && kit update"; \
		echo "Maintainers who still need workflow-source dogfood updates can rerun with STACK_UPDATE_COMPAT=1."; \
		exit 2; \
	fi
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/kit_update_stack.py --target "$(CURDIR)" \
		$(if $(KIT),--kit "$(KIT)",) \
		$(if $(WORKFLOW),--workflow "$(WORKFLOW)",) \
		$(if $(filter 1 true yes,$(STACK_UPDATE_JSON)),--json,) \
		$(if $(filter 1 true yes,$(STACK_UPDATE_FORCE_MANAGED)),--force-managed,) \
		$(if $(RUNTIME_ADAPTERS),--runtime-adapters "$(RUNTIME_ADAPTERS)",)

kit-refresh-stack:
	@if test "$(STACK_UPDATE_COMPAT)" != "1" -a "$(STACK_UPDATE_COMPAT)" != "true" -a "$(STACK_UPDATE_COMPAT)" != "yes"; then \
		echo "kit-refresh-stack is a deprecated maintainer compatibility target."; \
		echo "Ordinary target repos should use: kit update --dry-run && kit update"; \
		echo "Maintainers who still need workflow-source dogfood updates can rerun with STACK_UPDATE_COMPAT=1."; \
		exit 2; \
	fi
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/kit_update_stack.py --target "$(CURDIR)" --refresh \
		$(if $(KIT),--kit "$(KIT)",) \
		$(if $(WORKFLOW),--workflow "$(WORKFLOW)",) \
		$(if $(filter 1 true yes,$(STACK_UPDATE_JSON)),--json,) \
		$(if $(filter 1 true yes,$(STACK_UPDATE_FORCE_MANAGED)),--force-managed,) \
		$(if $(RUNTIME_ADAPTERS),--runtime-adapters "$(RUNTIME_ADAPTERS)",)

version-status:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/version.py status

version-check:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/version.py check

version-bump:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/version.py bump --bump "$(BUMP)"

agent-docs-lint:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/lint_agent_docs.py --strict-paths

agent-instruction-diet:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py instruction-diet --repo "$(CURDIR)" \
		$(if $(filter 1 true yes,$(INSTRUCTION_DIET_STRICT_PATHS)),--strict-paths,) \
		$(if $(filter 1 true yes,$(INSTRUCTION_DIET_JSON)),--json,)

agent-docs-localize:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/localize_doc_impact.py --working-tree --json

agent-docs-explain:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py docs-explain \
		--repo "$(CURDIR)" \
		$(if $(DOCS_EXPLAIN_QUESTION),--question "$(DOCS_EXPLAIN_QUESTION)",) \
		$(if $(DOCS_EXPLAIN_FOCUS),--focus "$(DOCS_EXPLAIN_FOCUS)",) \
		$(if $(DOCS_EXPLAIN_PATH),--path "$(DOCS_EXPLAIN_PATH)",) \
		$(if $(filter 1 true yes,$(DOCS_EXPLAIN_CHECK)),--check,) \
		$(if $(filter 1 true yes,$(DOCS_EXPLAIN_JSON)),--json,)

agent-docs-propose:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py docs-propose \
		--repo "$(CURDIR)" \
		--working-tree \
		$(if $(filter 1 true yes,$(DOCS_PROPOSE_WRITE_SIDECAR)),--write-sidecar,) \
		$(if $(filter 1 true yes,$(DOCS_PROPOSE_JSON)),--json,)

agent-changelog-update:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/repo_contract_kit.py changelog-update \
		--repo "$(CURDIR)" \
		--working-tree \
		$(if $(filter 1 true yes,$(CHANGELOG_UPDATE_CHECK)),--check,) \
		$(if $(CHANGELOG_UPDATE_BUMP),--bump "$(CHANGELOG_UPDATE_BUMP)",) \
		$(if $(CHANGELOG_UPDATE_VERSION),--version "$(CHANGELOG_UPDATE_VERSION)",) \
		$(if $(CHANGELOG_UPDATE_SECTION),--section "$(CHANGELOG_UPDATE_SECTION)",) \
		$(if $(CHANGELOG_UPDATE_SUMMARY),--summary "$(CHANGELOG_UPDATE_SUMMARY)",) \
		$(if $(filter 1 true yes,$(CHANGELOG_UPDATE_JSON)),--json,)

agent-token-budget:
	@PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_token_budget.py \
		$(if $(filter 1 true yes,$(TOKEN_BUDGET_JSON)),--json,) \
		$(if $(filter 1 true yes,$(TOKEN_BUDGET_STRICT)),--strict,)

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
