---
type: is
id: is-01m7jh99rfr5fncac2thwxce4d
title: 'PR #464 B1: a "more" row below a revealed page draws its page above the reader and sends focus 200 rows ahead'
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjm7dvfsqanbt2jtdyxfy
hold: null
hold_until: null
created_at: 2026-11-16T15:58:18.381Z
updated_at: 2026-11-16T16:33:02.188Z
started_at: 2026-11-16T15:58:28.907Z
closed_at: 2026-11-16T16:33:02.185Z
close_reason: "fixed in 288a055: a more row grows up only when the tree's selected row follows it; session step and Chrome step 13 fail without it. https://github.com/jlevy/metabrowser/pull/464#issuecomment-6922472756"
resolution: null
duplicate_of: null
---
Medium. Review B (follow-up, round 2) on PR #464: https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5922595963. src/metabrowser/static/app.js:3603-3643 (mountNextTreePage keeps the rows after any "more" row fixed and focuses the last row drawn), :9305-9309 (mountTreePageAt puts a second reveal's remainder row below its page, above the first's), docs/design-system.md:3279-3282. Fix: keep the rows after a "more" row in place only when the tree's selected row comes after it; otherwise grow down and focus the first row drawn. Session step (reveal f0905, then f0405, press the row after f0599, focus f0600), Chrome check (f600 in view), doc correction.
