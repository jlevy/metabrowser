---
type: is
id: is-01m774r967jvcvcx4btkpyfzeg
title: Per-main-tab retained surfaces
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:39.078Z
updated_at: 2026-11-15T06:12:33.023Z
---
Files, Commits, and Pulls each keep their own surface; a switch suspends instead of claiming the pane. Measured as main-tab switch painted-ready, blank frames, requests.
