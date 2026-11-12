---
type: is
id: is-01m78aemb09t352agy9ffdm67d
title: "PR #375 A1: three tests still assert the --show views line without keys"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ae0p02ghts4vw9h2vrmhp
hold: null
hold_until: null
created_at: 2026-11-12T16:46:28.703Z
updated_at: 2026-11-12T17:22:18.546Z
started_at: 2026-11-12T16:46:40.291Z
closed_at: 2026-11-12T17:22:18.545Z
close_reason: "Fixed in f509028a (test assertions keyed); test_cli_acquire.py:577 correct again under A3. Disposition: https://github.com/jlevy/metabrowser/pull/375#issuecomment-6830783051"
resolution: null
duplicate_of: null
---
High. PR #375 review A (https://github.com/jlevy/metabrowser/pull/375#pullrequestreview-5871448143). tests/test_cli_show_mode.py:97 and :106 and tests/test_cli_acquire.py:577 assert the views line without keys; show_cli.py _describe_view now appends the key. CI test and admitted-git jobs fail. Fix: update the assertions to the keyed line, and search for other literals.
