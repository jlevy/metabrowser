---
type: is
id: is-01m6t6db612aj6w19qbxhcrp9a
title: Rename the Git navigation tab to Commits
kind: task
status: in_progress
priority: 2
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T05:06:30.208Z
updated_at: 2026-11-07T05:38:23.749Z
started_at: 2026-11-07T05:07:08.055Z
---
Use Commits for the visible main navigation tab and its shortcut help. Keep the fixed second shortcut position and independently remembered tab selection. Verify the installed left-aligned Markdown/README layout with its right-side KPress TOC and compact drawer, update current documentation, and publish as a new stacked PR.

## Notes

Published PR #321 above #320 in native stack #302 at a7d3c0139a12204fc556da463dbc2c8e40f3bc1a. Independent final review approved; Qodo reports no material issues. Full make verify passed (4892 tests, nine expected skips, 384 golden scenarios, both audits, distribution and installed-package checks). Manual built-in-browser checks passed for Commits/shortcut Help, left-aligned README with desktop right TOC, and narrow TOC drawer navigation. Local installation and preview replacement delegated; final CI and installed-browser confirmation pending.
