---
type: is
id: is-01m7r5cnfs2h2yhkcgj238s73w
title: Separate the page from the window (FolderPage)
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-18-macos-folder-switching.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7r5cnya426kax3rszcj3h2w
parent_id: is-01m7r5cmz107gb7jxq0y6pp7fe
created_at: 2026-11-18T20:25:52.376Z
updated_at: 2026-11-18T20:25:52.841Z
---
PR 1. Move the web view and per-page state (navigation policy, page loads, reveal, page sheets, print, find, downloads) out of BrowserWindowController into a FolderPage view controller a session owns; the window controller keeps chrome and shows one page. No behavior change; existing app tests hold.
