---
type: is
id: is-01m3v7sx1x6w4pys73jw4w2wee
title: "Tests leave process-global state changed: reader pools, probe results, ignore cache, catalog revision"
kind: task
status: in_progress
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
hold: null
hold_until: null
created_at: 2026-10-01T08:02:59.257Z
updated_at: 2026-11-01T17:59:57.632Z
started_at: 2026-11-01T16:21:31.357Z
---
From PR #252 (mb-onzb) and its review, evidence in the PR body's table: tests leave these process globals changed without restoring them. git.tree_source._POOLS: test_github_pull_page_session.py::test_recording_is_what_a_served_pull_request_answers leaves a reader pool (at base too). cache.probe._RESULTS: 333 tests add a report keyed by device and inode; inode reuse could serve a stale report (not observed). tree._IGNORE_CACHE: 210 tests change it. dotenv._reported: 4 tests. events_route._CATALOG_REVISION: 5 tests advance a process-wide counter, and the two one-entry catalog caches are left filled by one test. server._EXTRA_ALLOWED_HOSTS: two tests add 127.0.0.1 and one removes it (no effect; the default list holds it). No test leaves changed: _PLUGIN_KIND_RULES, _FOLDER_MARKERS, HISTORY_SESSIONS, os.environ, cwd, served root, log adapter table, the metabrowser logger. Decide per global: a reset in the existing autouse fixture where a stale value can change a later test's verdict (probe results, ignore cache, catalog revision), or a stated reason it cannot. Do not add resets speculatively; show the order dependence first (full-suite item-reversed run). Also still open from #252: three sleeps not converted (test_browser_v2.py:517, :636, test_cache_update.py:384) and the whole-suite item-reversed run was inconclusive under load. Not labelled v0.12: CI passes in module-reversed order.

## Notes

2026-11-01: fixed in PR #276, open, CI green at its last read. Close when it merges; its required review has not run. Precautionary: the reset is in place, but no failure was traced to this state.
