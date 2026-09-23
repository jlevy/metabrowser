---
type: is
id: is-01m35t6gm3b2kvgb7fz43xh5yq
title: Normalize acquisition failures for Git pin show and API modes
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md
delegate: claude-code@spud10
labels:
  - release:v0.12.0
  - stack:pr216
dependencies:
  - type: blocks
    target: is-01m2nzb0geg0hkaapyvj0hdb49
  - type: blocks
    target: is-01m35tapm6wjnn235hr3s669b7
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
hold: null
hold_until: null
created_at: 2026-09-23T00:21:09.378Z
updated_at: 2026-09-23T03:55:19.502Z
started_at: 2026-09-23T03:31:06.683Z
closed_at: 2026-09-23T03:55:19.498Z
close_reason: Fixed on codex/v012-foundation-stabilization d06e4b58 (above stack tip 7a3bd1de). --show and non-cache --api acquire through the same async mapper (acquire_cli.acquire_for_cli) as --no-serve and cache --api. Failures while opening the pin after acquisition use an allowlist of path-free messages and log the original at debug. tests/test_cli_acquire_error_modes.py drives all four modes over timeout/too-large/unavailable/command, asserts one shared message per kind, runs below-floor refusal in every mode with the home absent or left empty, and checks a path-bearing lease-stage GitUnavailableError. 9 of 15 failed before the fix; all pass after.
resolution: null
duplicate_of: null
---
Confirmed at pushed PR #216 b3c001a9. src/metabrowser/cli/git_pin_cli.py:59-64 catches _ACQUIRE_CLI_ERRORS around acquire_file_source but not GitError. acquire_cli.acquire_published_source maps the same Git errors with _git_failure_message. Typer invocation with injected UnsupportedGitVersionError or GitTimeoutError returns CLIError for --no-serve and cache --api; --show README and --api /api/tree instead retain the raw Git exception, so the real entry point can traceback and disclose staging-path diagnostics. Share the async acquisition error mapper and add a table-driven regression through all four public modes. Preserve error causes and ensure below-floor refusal leaves the application home absent. Distinct from closed mb-rpo9 (acquire modes) and mb-9fmu (content routes).
