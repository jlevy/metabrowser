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

.PHONY: default install hooks-install format format-markdown lint lint-check test lock upgrade build verify clean

default: install format lint test

install:
	uv sync --all-extras --all-groups --frozen
	npm ci --silent

hooks-install: install
	npx --no-install lefthook install

lint:
	uv run python devtools/lint.py
	uv run python devtools/npm_policy.py
	uv run python devtools/public_hygiene.py

format:
	$(MAKE) format-markdown
	uv run ruff check --fix src tests devtools
	uv run ruff format src tests devtools
	# Locked wrappers invoke the exact tools in package-lock.json without fetching.
	uv run python -m devtools.biome format --write \
		src/metabrowser/static src/metabrowser/builtin_plugins tests/dom \
		biome.json package.json tsconfig.json tsconfig.legacy.json

format-markdown:
	uvx --exclude-newer-package 'flowmark-rs=2026-05-31T00:00:00Z' flowmark-rs@0.3.1 --auto --inplace --nobackup .

# Check-only lint, matching CI (does not modify files).
lint-check:
	uv run python devtools/lint.py --check
	uv run python devtools/npm_policy.py
	uv run python devtools/public_hygiene.py
	uvx --exclude-newer-package 'flowmark-rs=2026-05-31T00:00:00Z' flowmark-rs@0.3.1 --auto --check .

test:
	uv run pytest

lock:
	uv lock

upgrade:
	uv lock --upgrade
	uv sync --all-extras --all-groups --frozen

build:
	uv build --clear --no-build-isolation
	uv run python -m devtools.check_distribution

verify: install lint-check test build

clean:
	-rm -rf dist/
	-rm -rf *.egg-info/
	-rm -rf .pytest_cache/
	-rm -rf .ruff_cache/
	-rm -rf .mypy_cache/
	-rm -rf .venv/
	-find . -type d -name "__pycache__" -exec rm -rf {} +
