---
type: is
id: is-01m6f2mvfrvsttyk1wwsxbfjav
title: "PR #273 A3: _vertical_margins reads the first margin of a selector, not the winner"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f2mj3gymr1nybga3v8b9xw
hold: null
hold_until: null
created_at: 2026-11-02T21:29:03.223Z
updated_at: 2026-11-02T22:33:27.988Z
started_at: 2026-11-02T21:52:28.654Z
closed_at: 2026-11-02T22:33:27.987Z
close_reason: "fixed in 99fdcf43: last margin wins; test_a_later_margin_is_the_one_read"
resolution: null
duplicate_of: null
---
Low. tests/test_pull_page_route.py:101, :149-155. Review A: https://github.com/jlevy/metabrowser/pull/273#pullrequestreview-5743252755
