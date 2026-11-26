# Makefile for easy development workflows.
# See docs/development.md for docs.
# GitHub Actions use these targets so local and CI gates stay aligned.

.DEFAULT_GOAL := default
# Keep install and quality stages ordered even when callers pass `-j`.
.NOTPARALLEL:

# Safe default for every dependency resolution invoked through this Makefile.
UV_EXCLUDE_NEWER ?= 14 days
export UV_EXCLUDE_NEWER
# Prevent machine-global uv policy from changing the repository lock. Pass the
# checked-in configuration explicitly so every command is self-contained and
# reviewable instead of depending on an inherited UV_CONFIG_FILE setting.
UV := uv --config-file $(CURDIR)/uv.toml
UVX := uvx --config-file $(CURDIR)/uv.toml
UV_RUN := $(UV) run --frozen
# First-party exception reviewed in SUPPLY-CHAIN-SECURITY.md. The cutoff is
# package-scoped and only admits the exact formatter release pinned here.
FLOWMARK_VERSION := 0.3.2
FLOWMARK_EXCEPTION := 2026-07-16T00:00:00Z
FLOWMARK := $(UVX) --exclude-newer-package 'flowmark-rs=$(FLOWMARK_EXCEPTION)' flowmark-rs@$(FLOWMARK_VERSION)
# The lint targets fail a branch that adds an entry to CHANGELOG.md's Unreleased section
# since its merge base with this ref; entries go in changelog.d/ (devtools/changelog.py).
CHANGELOG_BASE ?= origin/main

# Some managed agent environments export pnpm-style npm variables that npm 11
# treats as unknown configuration. Repository policy lives in .npmrc, so prevent
# those ambient aliases from adding warnings or changing command behavior.
unexport NPM_CONFIG_FROZEN_LOCKFILE
unexport NPM_CONFIG_MINIMUM_RELEASE_AGE
# A host-level publication cutoff conflicts with the repository's release-age gate in
# npm 11. Repository installs must use the reviewed .npmrc policy instead.
unexport NPM_CONFIG_BEFORE

.PHONY: default install hooks-install biome-fix browser-types format format-markdown lint lint-check test test-parallel test-serial test-chrome test-goldens test-admitted-git audit lock upgrade build verify clean

default: install format lint test

install:
	# --locked also asserts uv.lock matches pyproject.toml and uv.toml, so a
	# stale or locally contaminated lock fails here instead of shipping.
	$(UV) sync --all-extras --all-groups --locked
	npm ci

hooks-install: install
	npx --no-install lefthook install

biome-fix:
	npx --no-install biome check --write --unsafe --no-errors-on-unmatched $(STAGED_FILES)

browser-types:
	npx --no-install tsc --noEmit -p tsconfig.json
	npx --no-install tsc --noEmit -p tsconfig.legacy.json
	npx --no-install tsc --noEmit -p apps/macos/webkit-gate/tsconfig.json

# A CI job calls each test tier's target directly, so each installs first, as `test` does.
format lint lint-check test test-parallel test-serial test-chrome test-goldens test-admitted-git audit build: | install

lint:
	$(UV_RUN) python -m devtools.lint
	$(UV_RUN) python -m devtools.public_hygiene
	$(UV_RUN) python -m devtools.check_file_type_colors --quiet
	$(UV_RUN) python -m devtools.check_tooltips
	$(UV_RUN) python -m devtools.check_supply_chain
	$(UV_RUN) python -m devtools.check_ci
	$(UV_RUN) python -m devtools.check_artifact_contracts
	$(UV_RUN) python -m devtools.check_parity
	$(UV_RUN) python -m devtools.check_plugin_deps
	$(UV_RUN) python -m devtools.check_app_contract check --against $(CHANGELOG_BASE)
	$(UV_RUN) python -m devtools.check_goldens
	$(UV_RUN) python -m devtools.changelog check --against $(CHANGELOG_BASE)

format:
	$(MAKE) format-markdown
	$(UV_RUN) ruff format src tests devtools explorations
	npx --no-install biome format --write \
		apps/macos/webkit-gate src/metabrowser/static src/metabrowser/builtin_plugins tests/dom \
		explorations \
		biome.json package.json tsconfig.json tsconfig.legacy.json

format-markdown:
	$(FLOWMARK) --auto --inplace --nobackup .

# Refresh vendored browser assets from lockfile-verified node_modules.
# Run after bumping a browser library pin in package.json; commit the
# resulting static/vendor/ changes. Tests verify manifest parity.
vendor-assets: install
	$(UV_RUN) python devtools/vendor_assets.py --write

# Check-only lint, matching CI (does not modify files).
lint-check:
	$(UV_RUN) python -m devtools.lint --check
	$(UV_RUN) python -m devtools.public_hygiene
	$(UV_RUN) python -m devtools.check_file_type_colors --quiet
	$(UV_RUN) python -m devtools.check_tooltips
	$(UV_RUN) python -m devtools.check_supply_chain
	$(UV_RUN) python -m devtools.check_ci
	$(UV_RUN) python -m devtools.check_artifact_contracts
	$(UV_RUN) python -m devtools.check_parity
	$(UV_RUN) python -m devtools.check_plugin_deps
	$(UV_RUN) python -m devtools.check_app_contract check --against $(CHANGELOG_BASE)
	$(UV_RUN) python -m devtools.check_goldens
	$(UV_RUN) python -m devtools.changelog check --against $(CHANGELOG_BASE)
	$(UV_RUN) python -m devtools.check_startup_scripts
	$(FLOWMARK) --auto --check .

# The tryscript goldens run with a failing gh first on PATH (tests/no-real-gh/gh), so
# none reaches a developer's signed-in gh; pytest has the same guard in tests/conftest.py.
#
# The server logs a request slower than 2 s to stderr, which a transcript captures, so
# a loaded machine changed what a golden recorded: at a load average near 100, nine
# `--api` requests of cli-api-cache.tryscript.md took 2.4 to 8.0 s and each printed the
# line. It is a wall-clock measurement and not behavior, so the threshold is put past
# tryscript's own 30 s command timeout, where it cannot fire before the command fails.
#
# A golden that serves writes no event log into the state directory of whoever runs it
# (METABROWSER_EVENT_LOG=0, as tests/conftest.py sets for pytest); one that reads the log
# names its own directory. Nor does a stand-in gh that fails make it probe the network
# (METABROWSER_NETWORK_PROBE=0, as tests/conftest.py also sets).
#
# `env` sets them all, so the same words work as a shell command and as the command
# devtools/run_goldens.py runs once for each golden.
TRYSCRIPT := env -u METABROWSER_CACHE_RESERVE_MB PATH="$(CURDIR)/tests/no-real-gh:$$PATH" METABROWSER_SLOW_SERVER_MS=60000 \
	METABROWSER_EVENT_LOG=0 METABROWSER_NETWORK_PROBE=0 npx --no-install tryscript
GOLDENS := tests/golden/*.tryscript.md
# How many golden files devtools/run_goldens.py runs at a time: one per processor of a CI
# runner, which has four. tryscript runs a file's commands one after another, each in a
# process of its own. On a shared 4-processor machine at a load average near 1, the 82
# goldens and their 457 commands took 307 s one at a time and 81 s four at a time, with
# the same verdict for every file (2026-11-17); the longest file alone is 38 s.
GOLDEN_JOBS ?= 4

# In CI a skip has to belong to a tier docs/e2e-testing.md names, or the test fails:
# a reason outside them means a test the suite is believed to run did not. Locally a
# platform or an old Git may skip more, so this is on only where CI is set, or where
# the caller sets the variable; see tests/suite_gates.py.
STRICT_SKIPS := $(if $(CI),METABROWSER_STRICT_SKIPS=1)

# Workers for the parallel tier and test-admitted-git, one per logical processor. xdist's
# `auto` counts physical cores through psutil, which this project installs, and a CI
# runner's four processors can be two cores with two threads each. A shared or loaded
# machine lowers it, as in `make test PYTEST_WORKERS=2`. Measured only at three workers
# (a shared 4-processor machine) and four (CI's runners), as the fast CI plan's Phase 1
# Measurements record; a machine with more processors may want a cap.
PYTEST_WORKERS ?= logical
# `SHARD=I/N` runs the Ith of N disjoint parts of a pytest tier (tests/suite_tiers.py) or
# of the goldens (devtools/run_goldens.py); empty runs the whole tier. The parts are dealt
# by the seconds CI measured (devtools/shard_weights.py), which `make shard-weights`
# refreshes.
SHARD ?=
# -rs names every skipped test with its reason, so a skip is read rather than counted,
# and --durations and --file-durations list the slowest tests and every test file
# (tests/suite_timing.py), so a run says where its time went. `make shard-weights` reads
# both from CI's logs to weigh the shards (devtools/refresh_shard_weights.py), which is
# why every file is listed, some 230 lines in a unit job's log, and why the serial and
# Chrome tiers, which are dealt by test, list every test (EVERY_TEST): a part of either
# holds few tests, but more than 25 once the heavy tests fill another part. A missing
# Node or Git stops the run; see tests/required_tools.py.
PYTEST := $(STRICT_SKIPS) $(UV_RUN) pytest -rs --durations=25 --file-durations=0 \
	$(if $(SHARD),--shard=$(SHARD))
EVERY_TEST := --durations=0
# The tiers' -m expressions, which tests/suite_tiers.py defines as TIERS: together they
# hold every test once, whatever is marked.
PARALLEL_TIER := not serial and not chrome
SERIAL_TIER := serial and not chrome
CHROME_TIER := chrome

# The default tier, as four parts that CI can also run one at a time. Each file of the
# parallel tier runs on one worker, its tests in order (--dist loadfile), so module-scoped
# fixtures behave as they do in one process. The serial and Chrome tiers run one test at
# a time, after the parallel tier and so never beside its workers.
#
# For the same reason a SHARD of the parallel tier holds whole files (--shard-by=file).
# Dealt by test, the CI unit jobs of run 44037230262 failed in two modules whose tests
# rely on an earlier one in the module: tests/test_cli_git_pin_golden.py, whose first
# test records the clone the rest reuse (bead mb-5zkq), and tests/test_github_pulls.py.
# Whole files stay the right deal once mb-5zkq is fixed, since a module-scoped fixture is
# then built once; the serial and Chrome tiers still deal by test.
test: test-parallel test-serial test-chrome test-goldens

test-parallel:
	$(PYTEST) -m "$(PARALLEL_TIER)" -n $(PYTEST_WORKERS) --dist loadfile --shard-by=file

test-serial:
	$(PYTEST) $(EVERY_TEST) -m "$(SERIAL_TIER)"

test-chrome:
	$(PYTEST) $(EVERY_TEST) -m "$(CHROME_TIER)"

test-goldens:
	$(UV_RUN) python -m devtools.run_goldens --jobs $(GOLDEN_JOBS) $(if $(SHARD),--shard $(SHARD)) '$(GOLDENS)' -- $(TRYSCRIPT)

# The size of the suite by area, at the working tree or at the commits in REFS, and with
# LOG the time each test file and golden took in that CI job log:
#   make test-report
#   make test-report REFS="origin/main ." LOG=run.log
# docs/e2e-testing.md ("Measuring the Suite") says how each number is taken.
.PHONY: test-report
test-report:
	$(UV_RUN) python -m devtools.suite_report $(REFS) $(if $(LOG),--log $(LOG))

# Each CI job's median and 90th percentile, push to green by kind of run, and reruns, over
# the newest runs of ci.yml as gh reads them; CI_REPORT_FLAGS passes devtools/ci_report.py
# its options:
#   make ci-report
#   make ci-report CI_REPORT_FLAGS="--runs 300 --branch main --steps --save attic/ci-runs"
# docs/e2e-testing.md ("Measuring CI") says how each number is taken.
.PHONY: ci-report
ci-report:
	$(UV_RUN) python -m devtools.ci_report $(CI_REPORT_FLAGS)

# Rewrite devtools/shard_weights.json, the seconds SHARD's parts are dealt by, from the
# newest green CI run on main as gh reads its job logs; SHARD_WEIGHTS_FLAGS passes
# devtools/refresh_shard_weights.py its options:
#   make shard-weights
#   make shard-weights SHARD_WEIGHTS_FLAGS="--run 45062416967"
# docs/e2e-testing.md ("Time limits and shards") says when to.
.PHONY: shard-weights
shard-weights:
	$(UV_RUN) python -m devtools.refresh_shard_weights $(SHARD_WEIGHTS_FLAGS)

# The baseline scale benchmark that docs/scale-benchmark.md records: one run of
# devtools/bench_serving.py per size on its synthetic corpus under .bench/, then one
# Markdown table. Both sizes stay under the serving cap (INVENTORY_MAX_FILES in
# settings.py). The cold scan is skipped because no figure in the table comes from it.
# Another registered inventory provider runs as `make benchmark BENCHMARK_PROVIDER=name`.
BENCHMARK_SIZES := 100000 300000
BENCHMARK_PROVIDER ?= python
.PHONY: benchmark
benchmark: | install
	@for files in $(BENCHMARK_SIZES); do \
		$(UV_RUN) python -m devtools.bench_serving --files $$files \
			--provider $(BENCHMARK_PROVIDER) --skip-cold-scan --label benchmark-$$files \
			--json .bench/benchmark-$(BENCHMARK_PROVIDER)-$$files.json || exit 1; \
	done
	@$(UV_RUN) python -m devtools.bench_serving --markdown \
		$(foreach files,$(BENCHMARK_SIZES),.bench/benchmark-$(BENCHMARK_PROVIDER)-$(files).json)

# Acquisition and store-read tests on a real Git the acquisition floor admits,
# with nothing patched. They skip on a Git below the floor. The CI admitted-git
# job builds each admitted release and sets METABROWSER_REQUIRE_ADMITTED_GIT, which
# turns that skip into a failure; see tests/admitted_git.py. A test that asks for the
# floor from a module this list leaves out fails; see tests/suite_gates.py. The list runs
# beside other workers, like the parallel tier, so the same gates fail a serial or chrome
# test in it.
ADMITTED_GIT_TESTS := \
	tests/test_git_file_ages.py \
	tests/test_git_revision_ages_routes.py \
	tests/test_git_full_clone_acceptance.py \
	tests/test_cli_live_acquire_golden.py \
	tests/test_cache_acquire.py \
	tests/test_cache_publish.py \
	tests/test_cache_store_rename.py \
	tests/test_cli_acquire.py \
	tests/test_cli_cache_acquire_golden.py \
	tests/test_cli_git_pin_golden.py \
	tests/test_serve_pin.py \
	tests/test_cache_update.py \
	tests/test_source_refresh.py \
	tests/test_cli_git_refresh_golden.py \
	tests/test_refresh_signals.py \
	tests/test_git_revision_open.py \
	tests/test_git_store_read_policy.py \
	tests/test_git_tree_source.py \
	tests/test_git_reader_recovery.py \
	tests/test_git_revision_content_routes.py \
	tests/test_git_revision_diff.py \
	tests/test_cache_resolve.py \
	tests/test_cli_github_url_golden.py \
	tests/test_acquire_stall_and_hangup.py \
	tests/test_acquire_phases.py \
	tests/test_github_pulls.py \
	tests/test_guided_review_route.py \
	tests/test_github_pull_list.py \
	tests/test_pulls_nav.py \
	tests/test_checkout_overlay.py \
	tests/test_checkout_revisions.py \
	tests/test_checkout_store.py \
	tests/test_source_ref_selector_origin_session.py \
	tests/test_cli_source_checkout_golden.py \
	tests/test_cli_checkout_store_golden.py \
	tests/test_github_checkout.py \
	tests/test_cli_github_checkout_golden.py \
	tests/test_cli_checkout_golden.py \
	tests/test_cli_github_pull_golden.py \
	tests/test_cli_github_pull_image_golden.py \
	tests/test_cli_github_pull_size_golden.py \
	tests/test_cli_github_pull_rendered_golden.py \
	tests/test_cli_github_pull_rendered_views_golden.py \
	tests/test_cli_github_pulls_golden.py \
	tests/test_cli_github_stacks_golden.py \
	tests/test_cli_github_stack_change_golden.py \
	tests/test_cli_github_stack_golden.py \
	tests/test_github_stack_change.py \
	tests/test_github_pull_stack.py \
	tests/test_cli_github_labels_golden.py \
	tests/test_cli_github_pull_files_golden.py \
	tests/test_cli_github_pull_files_summary_golden.py \
	tests/test_cli_github_pulls_prefetch_golden.py \
	tests/test_github_ref_pulls.py \
	tests/test_cli_github_ref_pulls_golden.py \
	tests/test_github_pull_files.py \
	tests/test_github_pull_files_summary.py \
	tests/test_github_drawn_from_disk.py \
	tests/test_cache_async_locks.py \
	tests/test_cli_no_serve_surface.py \
	tests/test_diff_view_file_session.py \
	tests/test_github_pull_page_session.py \
	tests/test_github_pulls_panel_session.py \
	tests/test_github_pull_files_tree_session.py \
	tests/test_github_serve.py \
	tests/test_source_freshness_session.py \
	tests/test_source_ref_selector_session.py \
	tests/test_key_reveal_session.py \
	tests/test_cli_acquire_error_modes.py \
	tests/test_cli_cache_recovery_golden.py \
	tests/test_source_refs.py \
	tests/test_mirror_heading_session.py \
	tests/test_diff_comparison_cache.py \
	tests/test_github_pull_manifests.py \
	tests/test_github_pull_record_swap.py \
	tests/test_github_comparison_recovery.py \
	tests/test_github_pull_route_probe.py \
	tests/test_github_pull_snapshot.py \
	tests/test_github_pull_publication.py \
	tests/test_app_contract_golden.py \
	tests/test_admitted_git_gate.py

test-admitted-git:
	$(STRICT_SKIPS) $(UV_RUN) pytest -rs --file-durations=25 -n $(PYTEST_WORKERS) --dist loadfile \
		$(if $(SHARD),--shard=$(SHARD) --shard-by=file) $(ADMITTED_GIT_TESTS)

# The outer tiers nothing in CI runs. docs/e2e-testing.md ("Test Tiers") says what each
# covers and when to run it.
.PHONY: test-macos test-live-github
test-macos test-live-github: | install

# Tests that need macOS: its extended ACLs, or a case-insensitive file system. They are
# part of `make test` on a Mac and skip on Linux. Here a skip is a failure, so this
# target cannot pass on a machine that cannot run them.
test-macos:
	METABROWSER_REQUIRE_MACOS_TIER=1 $(UV_RUN) pytest -rs -m macos_tier

# Read-only smoke tests against public repositories on github.com. They need the
# network, an admitted Git, and a gh signed in to github.com.
test-live-github:
	METABROWSER_LIVE_GITHUB=1 $(UV_RUN) pytest -rs -m live_github

# Regenerate every recorded fixture and golden after an intended surface change.
# The order is the dependency order: the recorders write the response fixtures the
# browserless sessions replay (tests/fixtures/*.json), tryscript then rewrites changed
# blocks with literal output and golden_fixup.py restores the elision patterns, and the
# in-process drivers rewrite tests/golden/*.txt. Every module that calls
# tests/golden_harness.py is in one of these two lists, and the recipe keeps this
# order, or `make lint-check` fails (devtools/check_goldens.py).
# devtools/golden_update.py runs a list with GOLDEN_UPDATE=1 and fails if any test in
# it was skipped, so a host without Node or with a Git below the acquisition floor
# cannot report that it regenerated what it skipped. Review the diff before committing.
GOLDEN_RECORDERS := \
	tests/test_source_kind_session.py \
	tests/test_mirror_heading_session.py \
	tests/test_source_freshness_session.py \
	tests/test_source_ref_selector_session.py \
	tests/test_source_ref_selector_origin_session.py \
	tests/test_key_reveal_session.py \
	tests/test_event_log_view_session.py \
	tests/test_table_view_session.py \
	tests/test_fsqlite_info_session.py \
	tests/test_fsqlite_tables_session.py \
	tests/test_sqlite_info_session.py \
	tests/test_sqlite_tables_session.py \
	tests/test_diff_view_file_session.py \
	tests/test_diff_markdown_session.py \
	tests/test_diff_structured_session.py \
	tests/test_pdf_surfaces_session.py \
	tests/test_github_pull_page_session.py \
	tests/test_cli_github_checkout_golden.py \
	tests/test_github_pulls_panel_session.py \
	tests/test_github_stack_change.py \
	tests/test_cli_github_stack_golden.py \
	tests/test_github_pull_files_summary.py \
	tests/test_github_pull_files_tree_session.py \
	tests/test_inert_toc.py \
	tests/test_inert_html.py
GOLDEN_DRIVERS := \
	tests/test_cli_golden.py \
	tests/test_serve_pin.py \
	tests/test_cli_cache_acquire_golden.py \
	tests/test_cli_cache_recovery_golden.py \
	tests/test_cli_live_acquire_golden.py \
	tests/test_cli_git_pin_golden.py \
	tests/test_cli_git_refresh_golden.py \
	tests/test_cli_github_url_golden.py \
	tests/test_cli_github_pull_golden.py \
	tests/test_cli_github_pull_image_golden.py \
	tests/test_cli_github_pull_size_golden.py \
	tests/test_cli_github_pull_rendered_golden.py \
	tests/test_cli_github_pull_rendered_views_golden.py \
	tests/test_cli_github_pulls_golden.py \
	tests/test_cli_github_stacks_golden.py \
	tests/test_cli_github_stack_change_golden.py \
	tests/test_cli_github_stack_golden.py \
	tests/test_cli_github_labels_golden.py \
	tests/test_cli_github_pull_files_golden.py \
	tests/test_cli_github_pull_files_summary_golden.py \
	tests/test_cli_github_pulls_prefetch_golden.py \
	tests/test_cli_github_ref_pulls_golden.py \
	tests/test_cli_checkout_golden.py \
	tests/test_cli_github_checkout_golden.py \
	tests/test_cli_source_checkout_golden.py \
	tests/test_cli_checkout_store_golden.py \
	tests/test_cli_present_golden.py \
	tests/test_app_contract_golden.py \
	tests/test_diff_comparison_cache.py \
	tests/test_agents_mapping_golden.py

golden-update:
	$(UV_RUN) python -m devtools.golden_update $(GOLDEN_RECORDERS)
	$(TRYSCRIPT) run --update '$(GOLDENS)' || true
	$(UV_RUN) python -m devtools.golden_fixup
	$(TRYSCRIPT) run '$(GOLDENS)'
	$(UV_RUN) python -m devtools.golden_update $(GOLDEN_DRIVERS)

audit:
	bash devtools/npm_audit.sh
	$(UV) --preview-features audit-command audit --frozen

lock:
	$(UV) lock

upgrade:
	$(UV) lock --upgrade
	$(UV) sync --all-extras --all-groups --frozen

build:
	$(UV) build --clear --no-build-isolation
	$(UV_RUN) python -m devtools.check_distribution

verify: install lint-check test audit build

# The native macOS app in apps/macos (README.md there). It needs macOS and Swift, so
# elsewhere these targets say so and succeed, and `verify` does not depend on them.
MACOS_APP_TARGETS := macos-build macos-test macos-app macos-run macos-dmg macos-release \
	macos-notarize macos-signing-check macos-check-release macos-clean macos-webkit-gate
.PHONY: $(MACOS_APP_TARGETS)
$(MACOS_APP_TARGETS):
ifeq ($(shell uname -s),Darwin)
	$(MAKE) -C apps/macos $(@:macos-%=%)
else
	@echo "$@: the macOS app builds only on macOS; skipping."
endif

clean:
	-rm -rf dist/
	-rm -rf *.egg-info/
	-rm -rf .pytest_cache/
	-rm -rf .ruff_cache/
	-rm -rf .mypy_cache/
	-rm -rf .venv/
	-rm -rf node_modules/
	-find . -type d -name "__pycache__" -exec rm -rf {} +
