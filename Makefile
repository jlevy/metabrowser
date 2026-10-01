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

# Some managed agent environments export pnpm-style npm variables that npm 11
# treats as unknown configuration. Repository policy lives in .npmrc, so prevent
# those ambient aliases from adding warnings or changing command behavior.
unexport NPM_CONFIG_FROZEN_LOCKFILE
unexport NPM_CONFIG_MINIMUM_RELEASE_AGE
# A host-level publication cutoff conflicts with the repository's release-age gate in
# npm 11. Repository installs must use the reviewed .npmrc policy instead.
unexport NPM_CONFIG_BEFORE

.PHONY: default install hooks-install biome-fix browser-types format format-markdown lint lint-check test test-admitted-git audit lock upgrade build verify clean

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

format lint lint-check test test-admitted-git audit build: | install

lint:
	$(UV_RUN) python -m devtools.lint
	$(UV_RUN) python -m devtools.public_hygiene
	$(UV_RUN) python -m devtools.check_file_type_colors --quiet
	$(UV_RUN) python -m devtools.check_tooltips
	$(UV_RUN) python -m devtools.check_supply_chain
	$(UV_RUN) python -m devtools.check_artifact_contracts
	$(UV_RUN) python -m devtools.check_parity
	$(UV_RUN) python -m devtools.check_goldens

format:
	$(MAKE) format-markdown
	$(UV_RUN) ruff format src tests devtools explorations
	npx --no-install biome format --write \
		src/metabrowser/static src/metabrowser/builtin_plugins tests/dom explorations \
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
	$(UV_RUN) python -m devtools.check_artifact_contracts
	$(UV_RUN) python -m devtools.check_parity
	$(UV_RUN) python -m devtools.check_goldens
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
TRYSCRIPT := PATH="$(CURDIR)/tests/no-real-gh:$$PATH" METABROWSER_SLOW_SERVER_MS=60000 \
	npx --no-install tryscript

# In CI a skip has to belong to a tier docs/e2e-testing.md names, or the test fails:
# a reason outside them means a test the suite is believed to run did not. Locally a
# platform or an old Git may skip more, so this is on only where CI is set, or where
# the caller sets the variable; see tests/suite_gates.py.
STRICT_SKIPS := $(if $(CI),METABROWSER_STRICT_SKIPS=1)

# The default tier. -rs names every skipped test with its reason, so a skip is read
# rather than counted, and --durations lists the slowest tests, so a run says where its
# time went. A missing Node or Git stops the run; see tests/required_tools.py.
test:
	$(STRICT_SKIPS) $(UV_RUN) pytest -rs --durations=25
	$(TRYSCRIPT) run 'tests/golden/*.tryscript.md'

# The size of the suite by area, at the working tree or at the commits in REFS, and with
# LOG the time each test file and golden took in that CI job log:
#   make test-report
#   make test-report REFS="origin/main ." LOG=run.log
# docs/e2e-testing.md ("Measuring the Suite") says how each number is taken.
.PHONY: test-report
test-report:
	$(UV_RUN) python -m devtools.suite_report $(REFS) $(if $(LOG),--log $(LOG))

# Acquisition and store-read tests on a real Git the acquisition floor admits,
# with nothing patched. They skip on a Git below the floor. The CI admitted-git
# job builds each admitted release and sets METABROWSER_REQUIRE_ADMITTED_GIT, which
# turns that skip into a failure; see tests/admitted_git.py. A test that asks for the
# floor from a module this list leaves out fails; see tests/suite_gates.py.
ADMITTED_GIT_TESTS := \
	tests/test_git_full_clone_acceptance.py \
	tests/test_cli_live_acquire_golden.py \
	tests/test_cache_acquire.py \
	tests/test_cache_publish.py \
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
	tests/test_git_revision_content_routes.py \
	tests/test_git_revision_diff.py \
	tests/test_cache_resolve.py \
	tests/test_cli_github_url_golden.py \
	tests/test_acquire_stall_and_hangup.py \
	tests/test_acquire_phases.py \
	tests/test_github_pulls.py \
	tests/test_cli_github_pull_golden.py \
	tests/test_cache_async_locks.py \
	tests/test_cli_no_serve_surface.py \
	tests/test_diff_view_file_session.py \
	tests/test_github_pull_page_session.py \
	tests/test_github_serve.py \
	tests/test_source_freshness_session.py \
	tests/test_source_ref_selector_session.py \
	tests/test_cli_acquire_error_modes.py \
	tests/test_cli_cache_recovery_golden.py \
	tests/test_source_refs.py \
	tests/test_admitted_git_gate.py

test-admitted-git:
	$(STRICT_SKIPS) $(UV_RUN) pytest -rs $(ADMITTED_GIT_TESTS)

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
	tests/test_source_freshness_session.py \
	tests/test_source_ref_selector_session.py \
	tests/test_diff_view_file_session.py \
	tests/test_github_pull_page_session.py \
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
	tests/test_cli_github_pull_golden.py

golden-update:
	$(UV_RUN) python -m devtools.golden_update $(GOLDEN_RECORDERS)
	$(TRYSCRIPT) run --update 'tests/golden/*.tryscript.md' || true
	$(UV_RUN) python -m devtools.golden_fixup
	$(TRYSCRIPT) run 'tests/golden/*.tryscript.md'
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

clean:
	-rm -rf dist/
	-rm -rf *.egg-info/
	-rm -rf .pytest_cache/
	-rm -rf .ruff_cache/
	-rm -rf .mypy_cache/
	-rm -rf .venv/
	-rm -rf node_modules/
	-find . -type d -name "__pycache__" -exec rm -rf {} +
