# Makefile for easy development workflows.
# See docs/development.md for docs.
# GitHub Actions use these targets so local and CI gates stay aligned.

.DEFAULT_GOAL := default

# Safe default for every dependency resolution invoked through this Makefile.
UV_EXCLUDE_NEWER ?= 14 days
export UV_EXCLUDE_NEWER
# Prevent machine-global uv policy from changing the repository lock. All Make
# targets use the checked-in configuration file explicitly.
UV_CONFIG_FILE ?= $(CURDIR)/uv.toml
export UV_CONFIG_FILE
UV_RUN := uv run --frozen

# Some managed agent environments export pnpm-style npm variables that npm 11
# treats as unknown configuration. Repository policy lives in .npmrc, so prevent
# those ambient aliases from adding warnings or changing command behavior.
unexport NPM_CONFIG_FROZEN_LOCKFILE
unexport NPM_CONFIG_MINIMUM_RELEASE_AGE

.PHONY: default install hooks-install format format-markdown lint lint-check test audit lock upgrade build verify clean

default: install
	$(MAKE) SKIP_INSTALL=1 format
	$(MAKE) SKIP_INSTALL=1 lint
	$(MAKE) SKIP_INSTALL=1 test

install:
	# --locked also asserts uv.lock matches pyproject.toml and uv.toml, so a
	# stale or locally contaminated lock fails here instead of shipping.
	uv sync --all-extras --all-groups --locked
	npm ci

hooks-install: install
	npx --no-install lefthook install

# Top-level quality gates cannot start until both environments are installed
# from their locks. The default target invokes its mutating format/lint/test
# stages serially and tells those recursive makes that installation is complete.
ifeq ($(SKIP_INSTALL),)
format lint: | install
lint-check test audit build: | install
endif

lint:
	$(UV_RUN) python devtools/lint.py
	$(UV_RUN) python devtools/npm_policy.py
	$(UV_RUN) python devtools/public_hygiene.py

format:
	$(MAKE) format-markdown
	$(UV_RUN) ruff check --fix src tests devtools
	$(UV_RUN) ruff format src tests devtools
	# Locked wrappers invoke the exact tools in package-lock.json without fetching.
	$(UV_RUN) python -m devtools.biome format --write \
		src/metabrowser/static src/metabrowser/builtin_plugins tests/dom \
		biome.json package.json tsconfig.json tsconfig.legacy.json

format-markdown:
	uvx --exclude-newer-package 'flowmark-rs=2026-05-31T00:00:00Z' flowmark-rs@0.3.1 --auto --inplace --nobackup .

# Check-only lint, matching CI (does not modify files).
lint-check:
	$(UV_RUN) python devtools/lint.py --check
	$(UV_RUN) python devtools/npm_policy.py
	$(UV_RUN) python devtools/public_hygiene.py
	uvx --exclude-newer-package 'flowmark-rs=2026-05-31T00:00:00Z' flowmark-rs@0.3.1 --auto --check .

test:
	$(UV_RUN) pytest

audit:
	npm audit --audit-level=moderate
	uv --preview-features audit-command audit --frozen

lock:
	uv lock

upgrade:
	uv lock --upgrade
	uv sync --all-extras --all-groups --frozen

build:
	uv build --clear --no-build-isolation
	$(UV_RUN) python -m devtools.check_distribution

verify: install lint-check test audit build

clean:
	-rm -rf dist/
	-rm -rf *.egg-info/
	-rm -rf .pytest_cache/
	-rm -rf .ruff_cache/
	-rm -rf .mypy_cache/
	-rm -rf .venv/
	-find . -type d -name "__pycache__" -exec rm -rf {} +
