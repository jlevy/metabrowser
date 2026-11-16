---
type: is
id: is-01m7h0xks6dq30jg3djr0qw736
title: "PR #455 C1: startupScriptPaths keeps a script the browser's cache answered, against its comment and test"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h0wnsjyz9enemj0de4q5wg
hold: null
hold_until: null
created_at: 2026-11-16T01:53:03.781Z
updated_at: 2026-11-16T02:11:23.370Z
started_at: 2026-11-16T01:53:19.344Z
closed_at: 2026-11-16T02:11:23.369Z
close_reason: "C1 fixed in bea3f5c25 (option b): probe.js filters transferSize > 0 and encodedBodySize > 0; fixture in Chrome's shape fails before and passes after."
resolution: null
duplicate_of: null
---
Severity: Low. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review C (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914139612), finding C1. References: explorations/performance-loop/probe.js:37-49; run.py:858-861; tests/test_check_startup_scripts.py:342-352.
