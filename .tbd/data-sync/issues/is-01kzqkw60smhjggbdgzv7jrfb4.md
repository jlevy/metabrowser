---
type: is
id: is-01kzqkw60smhjggbdgzv7jrfb4
title: "PR 28 review R6/R7: live overlay rows omit the compound extension"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzqkvjhnr72wwk0cz3pmq7zp
created_at: 2026-08-11T05:14:11.858Z
updated_at: 2026-08-11T05:26:27.477Z
closed_at: 2026-08-11T05:26:27.476Z
close_reason: recentEntryFromFsEntry carries entry.ext; regression test pins it. Fixed in b37c6dd.
---
src/metabrowser/static/app.js recentEntryFromFsEntry no longer mirrors _file_entry_to_recent_dict: it omits the inventory compound extension, so a file that reaches the recency panel only through the live fs.change overlay is matched on its last dotted suffix while rendered rows are matched on the index tail. A compound pick can hide it. Two Bugbot comments report the same defect.
