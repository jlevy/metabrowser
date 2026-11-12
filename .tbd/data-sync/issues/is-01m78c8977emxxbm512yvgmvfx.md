---
type: is
id: is-01m78c8977emxxbm512yvgmvfx
title: "Landing outside the inline budget: reveal its path without moving the tree"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T17:17:57.855Z
updated_at: 2026-11-12T17:17:57.855Z
---
From review C (C5, not a regression) on jlevy/metabrowser#370. A landing whose path the shell does not inline (a folder wider than 200 entries, more than 300 rows, or deeper than 8) still reveals its path with no input and moves the tree: 8 folders of 251 entries 0.175; 302 rows over 2 folders 0.081; one folder of 201 entries 0.043; tests/test_pulls_nav.py in this repository (tests/ has 352 entries) 0.051 and the row is not revealed. Options: inline a window of a wide folder around the landing row with a Show N more row, reserve the revealed rows' space, or reveal behind the first paint. Measure as tree region movement on deep and wide landings.
