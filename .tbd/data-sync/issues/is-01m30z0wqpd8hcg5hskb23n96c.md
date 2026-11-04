---
type: is
id: is-01m30z0wqpd8hcg5hskb23n96c
title: bench runtime identity breaks when the venv path exceeds the shebang limit
kind: bug
status: closed
priority: 3
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
hold: null
hold_until: null
created_at: 2026-09-21T03:09:15.893Z
updated_at: 2026-11-04T17:14:29.675Z
started_at: 2026-11-01T16:05:46.662Z
closed_at: 2026-11-04T17:14:29.675Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
devtools/bench_serving.py resolve_metab_build/runtime_identity resolves the metab console script and then runs a Python snippet through the interpreter named in its shebang. When a checkout's .venv/bin/python path is longer than the 127-character shebang limit, uv writes a '#!/bin/sh' wrapper instead of a python shebang, so the snippet is handed to /bin/sh and exits 2. tests/test_bench_navigation.py::test_actual_build_runtime_includes_loaded_dependency_versions then fails for a reason that has nothing to do with the change under test. Observed with a worktree whose venv python path was 132 characters. Fix: run the snippet with an interpreter the tool resolves itself (sys.executable of the target venv, or 'metab' plus a dedicated subcommand) rather than trusting the console script's shebang.

## Notes

2026-11-01: fixed in PR #274, open, CI green at its last read. Close when it merges; its required review has not run.
