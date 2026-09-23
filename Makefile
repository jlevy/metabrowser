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

format:
	$(MAKE) format-markdown
	$(UV_RUN) ruff format src tests devtools explorations
	npx --no-install biome format --write \
		devtools/artifact-contract-browser-check.mjs \
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
	$(FLOWMARK) --auto --check .

test:
	$(UV_RUN) pytest
	npx --no-install tryscript run 'tests/golden/*.tryscript.md'

# Acquisition and store-read tests on a real Git the acquisition floor admits,
# with nothing patched. They skip on a Git below the floor. The CI admitted-git
# job builds each admitted release and sets METABROWSER_REQUIRE_ADMITTED_GIT, which
# turns that skip into a failure; see tests/admitted_git.py.
ADMITTED_GIT_TESTS := \
	tests/test_git_lazy_fetch_acceptance.py \
	tests/test_cli_live_acquire_golden.py \
	tests/test_cache_acquire.py \
	tests/test_cache_publish.py \
	tests/test_cli_acquire.py \
	tests/test_cli_cache_acquire_golden.py \
	tests/test_cli_git_pin_golden.py \
	tests/test_cli_git_pin_show_selection.py \
	tests/test_git_revision_lease.py \
	tests/test_git_store_read_policy.py \
	tests/test_git_tree_source.py \
	tests/test_git_revision_content_routes.py \
	tests/test_git_revision_diff.py

test-admitted-git:
	$(UV_RUN) pytest -rs $(ADMITTED_GIT_TESTS)

# Regenerate the CLI console goldens after an intended surface change.
# tryscript rewrites changed blocks with literal output, golden_fixup.py
# restores the elision patterns, and the pytest goldens (serve banners,
# file:// acquire and recovery, file:// pin, live acquire) are rewritten in
# place. The served source-kind fixture is recorded first because a tryscript
# session reads it. Review the diff before committing.
golden-update:
	GOLDEN_UPDATE=1 $(UV_RUN) pytest tests/test_source_kind_session.py
	npx --no-install tryscript run --update 'tests/golden/*.tryscript.md' || true
	$(UV_RUN) python devtools/golden_fixup.py
	npx --no-install tryscript run 'tests/golden/*.tryscript.md'
	GOLDEN_UPDATE=1 $(UV_RUN) pytest tests/test_cli_golden.py tests/test_cli_cache_acquire_golden.py \
		tests/test_cli_cache_recovery_golden.py tests/test_cli_git_pin_golden.py \
		tests/test_cli_live_acquire_golden.py

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
