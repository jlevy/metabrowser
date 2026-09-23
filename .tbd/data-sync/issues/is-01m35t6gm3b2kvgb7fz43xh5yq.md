---
type: is
id: is-01m35t6gm3b2kvgb7fz43xh5yq
title: Normalize acquisition failures for Git pin show and API modes
kind: bug
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md
labels:
  - release:v0.12.0
  - stack:pr216
dependencies:
  - type: blocks
    target: is-01m2nzb0geg0hkaapyvj0hdb49
  - type: blocks
    target: is-01m35tapm6wjnn235hr3s669b7
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-23T00:21:09.378Z
updated_at: 2026-09-23T00:23:26.596Z
---
Confirmed at pushed PR #216 b3c001a9. src/metabrowser/cli/git_pin_cli.py:59-64 catches _ACQUIRE_CLI_ERRORS around acquire_file_source but not GitError. acquire_cli.acquire_published_source maps the same Git errors with _git_failure_message. Typer invocation with injected UnsupportedGitVersionError or GitTimeoutError returns CLIError for --no-serve and cache --api; --show README and --api /api/tree instead retain the raw Git exception, so the real entry point can traceback and disclose staging-path diagnostics. Share the async acquisition error mapper and add a table-driven regression through all four public modes. Preserve error causes and ensure below-floor refusal leaves the application home absent. Distinct from closed mb-rpo9 (acquire modes) and mb-9fmu (content routes).
