---
type: is
id: is-01m6sxjyqf3b1z01p3gzzjpwty
title: Align the PR header state icon with the title
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m6sxmwx9fjjnft6mvavs5c7h
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T02:32:16.878Z
updated_at: 2026-11-07T03:38:20.997Z
started_at: 2026-11-07T02:33:20.380Z
---
Use the same colored PR state icon as the Pulls navigation at title scale, to the left of the PR title. Keep the Open/Draft/Closed/Merged badge below with its state color and text, omitting the duplicate icon. Preserve accessible state text, title wrapping, tab alignment, and layout across narrow and wide panes.

## Notes

Implemented in 63ce1003, merged forward at 5550f7c0. Real Open and Merged PRs in the browser show a title-sized decorative state icon on the left and text-only colored badge below. Mounted-page and design assertions pass.
