---
type: is
id: is-01m2ysx718x3rdsx317thsd81s
title: "PR 216 R5: avoid full-index rescans for every Git directory"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m2yryd6had8zdvj8eag4a4v4
created_at: 2026-09-20T07:01:23.617Z
updated_at: 2026-09-20T07:01:23.617Z
---
GitBlobIndex.tally and _git_filtered_tally scan every blob per directory, including _rollup_entries_from_index. Measured 1000/2000/4000 single-file directories at 0.179/0.778/1.852 seconds; synchronous request work scales quadratically. Build sorted name/range indexing and restrict each tally to its subtree, test prefix boundaries and nontrivial nested totals, remeasure.
