---
type: is
id: is-01m6f51bschh98hn3w6r9pdenw
title: "PR #277 B2: duplicate attributes: the server keeps the last, a browser keeps the first"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m6f50p52sbg40g9qx5rc11h1
created_at: 2026-11-02T22:10:50.282Z
updated_at: 2026-11-02T22:38:19.403Z
---
Low, pre-existing on main (inert_html.py values = dict(attrs), line 421 at c934a0b4, line 431 at this layer). Server: <img src=docs/a.png src=https://example.com/evil.png alt=a> becomes a link to the second value; a browser's parse keeps the first and the page builds an img. Both outcomes are allowlisted, the page sanitizes the server's single-attribute output, and KPress collapses duplicates first. Fix: keep the first occurrence with setdefault, add a duplicate-src and a duplicate-loading entry to the hostile corpus in tests/test_inert_html.py. PR #277, review B: https://github.com/jlevy/metabrowser/pull/277#pullrequestreview-5743502907

## Notes

Deferred from PR #277 review B: waiting on the v0.12 stack landing, so the fix goes up as its own change against main, where this code already is (inert_html.py, values = dict(attrs), line 421 at c934a0b4). Checked on 2026-11-02: reproduced on this layer. <img src=docs/a.png src=https://example.com/evil.png alt=a> hardens to a link to the second value, the reverse order keeps the in-tree image. Both outcomes are allowlisted, so no path to harm was found. Fix: keep the first occurrence with setdefault, and add a duplicate-src and a duplicate-loading entry to the hostile corpus in tests/test_inert_html.py so both layers are compared on them.
