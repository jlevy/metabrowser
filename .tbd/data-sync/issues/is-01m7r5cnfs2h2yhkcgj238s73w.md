---
type: is
id: is-01m7r5cnfs2h2yhkcgj238s73w
title: Separate the page from the window (FolderPage)
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-18-macos-folder-switching.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m7r5cnya426kax3rszcj3h2w
parent_id: is-01m7r5cmz107gb7jxq0y6pp7fe
hold: null
hold_until: null
created_at: 2026-11-18T20:25:52.376Z
updated_at: 2026-11-19T01:31:41.435Z
started_at: 2026-11-18T20:58:34.561Z
closed_at: 2026-11-19T01:31:41.433Z
close_reason: Merged in stack 579 (jlevy/metabrowser#565-#578) as 74d8d61
resolution: null
duplicate_of: null
---
PR 1. Move the web view and per-page state (navigation policy, page loads, reveal, page sheets, print, find, downloads) out of BrowserWindowController into a FolderPage view controller a session owns; the window controller keeps chrome and shows one page. No behavior change; existing app tests hold.
