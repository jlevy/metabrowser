---
type: is
id: is-01m7wys3bp2ndx4v4m26exf0hz
title: File ages, recency, and Files-tab grouping
kind: epic
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T17:06:31.923Z
updated_at: 2026-11-20T17:06:31.923Z
---
The Files tab groups, filters and dates what it lists: Group by (By age, By file type), Modified within, Recent, and each entry's age. On a folder the ages come from the inventory; on a Git revision they come from each file's last commit (git last-modified), which landed in #643 and #652.

What remains: a submodule entry is in no age group (mb-e3mn); directories in Recent results (mb-f42e); a folder header's age label that changes width moves its neighbours (mb-v4u6); filter-menu counts and a hidden file's note while tallies are unknown (mb-v2ls, mb-nutq); row positions and queued passes in the tree (mb-jdk0, mb-l2xc); the Group by session's failure mode and first-click case (mb-2fgr, mb-4d7s); one filter count (mb-zo3t); and the file-tree spacing (mb-8xcu, deferred). A cacheable recency filter belongs to mb-48vd.
