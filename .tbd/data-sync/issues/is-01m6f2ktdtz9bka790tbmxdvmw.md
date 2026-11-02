---
type: is
id: is-01m6f2ktdtz9bka790tbmxdvmw
title: "PR #274 A1: wrapped-launcher regex pins an apostrophe escape uv does not write"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f2kt0jwn6mx6es1wg9w3b8
hold: null
hold_until: null
created_at: 2026-11-02T21:28:29.369Z
updated_at: 2026-11-02T21:50:24.350Z
started_at: 2026-11-02T21:28:33.181Z
closed_at: 2026-11-02T21:50:24.347Z
close_reason: "fixed in 181518e; confirmed by test_split_console_launcher_finds_the_interpreter_in_either_form and a real uv 0.12.8 launcher. Reply: https://github.com/jlevy/metabrowser/pull/274#issuecomment-6589345714"
resolution: null
duplicate_of: null
---
Low. devtools/bench_serving.py:282-286,:303; tests/test_bench_serving.py:208. Review A: https://github.com/jlevy/metabrowser/pull/274#pullrequestreview-5743230239
