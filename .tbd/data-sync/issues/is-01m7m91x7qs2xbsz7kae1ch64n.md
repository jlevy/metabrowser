---
type: is
id: is-01m7m91x7qs2xbsz7kae1ch64n
title: "Flake: test_golden_pull_files_failures saw no account_changed stamp on disk in the command after it (run 44043888346)"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
hold: null
hold_until: null
created_at: 2026-11-17T08:12:56.439Z
updated_at: 2026-11-17T08:16:02.342Z
started_at: 2026-11-17T08:16:02.342Z
---
Seen once, in unit (3.13, 1/2) of CI run 44043888346 (jlevy/metabrowser#504 at e6f77bfb3; the other seven unit legs and 3 earlier runs passed it): tests/test_cli_github_pull_files_golden.py::test_golden_pull_files_failures failed its golden, cli-github-pull-files-failures.txt, at the command after the account-changed refresh (the gh-missing case, golden line 550).

The test's own asserts on the account-changed refresh passed: the CLI printed, after waiting for the job, last_refresh.outcome account_changed and state stale. But the next metab process, reading the record when it started its refresh, saw state current, last_refresh null, refreshing true, where the golden records stale and account_changed. So the account_changed stamp was not on disk, or was overwritten, between one CLI process and the next.

Where to look: src/metabrowser/builtin_plugins/github/pull_files_refresh.py, refresh_pull_files, which writes the stamp with write_files_refresh after the job, and _write, which logs at debug and drops an OSError writing the list; and whether the CLI prints the envelope before the stamp write has finished. mb-l2yn fixed the same scenario's list state for PR #279.

The module ran whole on one xdist worker, in order (--shard-by=file), as under Phase 1's make test, so this is not a shard-order dependence. Not rerun by the implementing agent; reported to the coordinator.
