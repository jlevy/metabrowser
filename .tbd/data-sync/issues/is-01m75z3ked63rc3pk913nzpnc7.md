---
type: is
id: is-01m75z3ked63rc3pk913nzpnc7
title: "PR #354 A7: alignRefreshing flushes style over the whole list on rebuild"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m75z31wt2khnr26spwbyy984
hold: null
hold_until: null
created_at: 2026-11-11T18:49:44.140Z
updated_at: 2026-11-11T19:23:50.866Z
started_at: 2026-11-11T18:55:30.690Z
closed_at: 2026-11-11T19:23:50.865Z
close_reason: "declined: measured in headless Chrome 152 at the tree's 111-row window, alignRefreshing adds at most ~0.4 ms over the style recalc any insert forces (1.6 ms vs 1.2 ms with 40 rebuilt; 2.1 vs 2.1 ms with 111); a scoped version measured slower (9.4 ms with 40 rebuilt)"
resolution: null
duplicate_of: null
---
Suggestion. Measure during a refresh-time rebuild of a large list; scope to rows just built if more than a few ms. Review: https://github.com/jlevy/metabrowser/pull/354#pullrequestreview-5863835475
