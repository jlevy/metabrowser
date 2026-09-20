---
type: is
id: is-01m2ysx718x3rdsx317thsd81s
title: "PR 216 R5: avoid full-index rescans for every Git directory"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m2yryd6had8zdvj8eag4a4v4
created_at: 2026-09-20T07:01:23.617Z
updated_at: 2026-09-20T07:15:21.787Z
closed_at: 2026-09-20T07:15:21.784Z
close_reason: "Fixed in bc8dd72b: GitBlobIndex tallies use sorted prefix spans so sibling string prefixes are excluded and directory scans stay linear."
resolution: null
duplicate_of: null
---
GitBlobIndex.tally and _git_filtered_tally scan every blob per directory, including _rollup_entries_from_index. Measured 1000/2000/4000 single-file directories at 0.179/0.778/1.852 seconds; synchronous request work scales quadratically. Build sorted name/range indexing and restrict each tally to its subtree, test prefix boundaries and nontrivial nested totals, remeasure.
