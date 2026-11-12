---
type: is
id: is-01m78xw5vemtmrp161x5j4wkvh
title: "PR #383 A2: no check ties built-in plugin letters c, g, h, l to the reserved table"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78xvnbykdp66qwvmwnrfzdp
hold: null
hold_until: null
created_at: 2026-11-12T22:25:55.565Z
updated_at: 2026-11-12T22:49:54.997Z
started_at: 2026-11-12T22:47:38.244Z
closed_at: 2026-11-12T22:49:54.996Z
close_reason: "fixed in 9795f0be: tests/test_keymap.py::test_the_built_in_plugins_keys_are_not_reserved reads C, G, H from PULL_TABS (github/pull-page.js) and L from renderDiffToolbar (diff/diff-view.js), requires these be the only shortcuts.attach() calls in builtin_plugins, and checks them against serialize_reserved_shell_keys() and reserved_keys_for('pull-request'); with g added to RESERVED_SHELL_KEYS it fails."
resolution: null
duplicate_of: null
---
Low. PR #383, review A (https://github.com/jlevy/metabrowser/pull/383#pullrequestreview-5882935821). tests/dom/github-pull-page-mount-behavior.js:596-604 serves a hand-written RESERVED_SHELL_KEYS; nothing compares it to keymap.py, so reserving c/g/h/l later would leave the golden green while production refuses the key. Fix: pytest that c, g, h, l are not reserved (sources pull-page.js PULL_TABS, diff-view.js renderDiffToolbar), or have the session read the served table.
