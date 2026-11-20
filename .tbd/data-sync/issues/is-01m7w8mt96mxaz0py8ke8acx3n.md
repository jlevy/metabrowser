---
type: is
id: is-01m7w8mt96mxaz0py8ke8acx3n
title: A submodule entry is in no age group on a Git revision
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys3bp2ndx4v4m26exf0hz
created_at: 2026-11-20T10:39:42.882Z
updated_at: 2026-11-20T17:08:47.600Z
---
Found by senior review A of #652 (A10). A gitlink has no time: the file ages answer dates blobs only, so under group_by=age or a recency window _git_entry_visible keeps no gitlink row, and an age grouping lists none of a repository's submodules (the ungrouped tree and By file type list them). Document: design-system.md and arch-git.md say a submodule is in no age group. To fix: treat a gitlink as an undated entry, which also needs the Undated group to show when it holds only gitlinks (groups_payload shows a group only when its file count is above zero), so the filtered 'entries' count of a revision's group has to count them. Parent: mb-3401.
