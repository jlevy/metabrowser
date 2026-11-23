---
type: is
id: is-01m83ce1ntnt27qc8eyxpwqyz7
title: "PR #722 A6: consider per-child priority instead of per-directory expansion"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m836qya23kghgk2m3t9em8nc
created_at: 2026-11-23T05:00:36.404Z
updated_at: 2026-11-23T05:00:41.780Z
---
Review A on https://github.com/jlevy/metabrowser/pull/722, finding A6 (suggestion): consider per-child priority instead of per-directory expansion.

Tracked as mb-ibu9, waiting on a design decision: whether the node budget should rank children across folders instead of expanding a folder's leading children whole. On this repository 87% of the 1,200 nodes were files, which is the cost this would address; the stack keeps per-folder expansion.
