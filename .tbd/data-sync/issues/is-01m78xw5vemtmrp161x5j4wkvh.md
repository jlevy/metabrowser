---
type: is
id: is-01m78xw5vemtmrp161x5j4wkvh
title: "PR #383 A2: no check ties built-in plugin letters c, g, h, l to the reserved table"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m78xvnbykdp66qwvmwnrfzdp
created_at: 2026-11-12T22:25:55.565Z
updated_at: 2026-11-12T22:25:55.565Z
---
Low. PR #383, review A (https://github.com/jlevy/metabrowser/pull/383#pullrequestreview-5882935821). tests/dom/github-pull-page-mount-behavior.js:596-604 serves a hand-written RESERVED_SHELL_KEYS; nothing compares it to keymap.py, so reserving c/g/h/l later would leave the golden green while production refuses the key. Fix: pytest that c, g, h, l are not reserved (sources pull-page.js PULL_TABS, diff-view.js renderDiffToolbar), or have the session read the served table.
