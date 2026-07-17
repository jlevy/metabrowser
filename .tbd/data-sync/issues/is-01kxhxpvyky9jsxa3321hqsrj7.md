---
type: is
id: is-01kxhxpvyky9jsxa3321hqsrj7
title: Make metab the canonical CLI with metabrowser alias
kind: feature
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-15T03:39:13.234Z
updated_at: 2026-07-17T21:16:35.049Z
closed_at: 2026-07-15T03:55:18.448Z
close_reason: Implemented metab as the canonical CLI, retained metabrowser as a tested compatibility alias, migrated code/tests/docs/specs, and passed local and PR release gates.
---
Publish metab as the canonical short console command while retaining metabrowser as a compatibility alias and package-name uvx entry point. Migrate executable invocations, remote spawning, diagnostics, tests, release smoke checks, and public documentation without renaming the PyPI package, Python imports, plugin entry-point group, logger namespace, repository, or browser globals.
