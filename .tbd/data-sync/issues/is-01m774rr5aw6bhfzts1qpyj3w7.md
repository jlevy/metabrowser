---
type: is
id: is-01m774rr5aw6bhfzts1qpyj3w7
title: "Layer 3: named activation paths and focus hooks"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md
labels:
  - layer-3
dependencies:
  - type: blocks
    target: is-01m774rrky1bpnkwshfqy4vqrz
parent_id: is-01m76jgfxbadse383jypkzwpm9
created_at: 2026-11-12T05:47:54.409Z
updated_at: 2026-11-12T07:31:10.659Z
---
Design > Badge Targets > Activation. selectPreviewTab extracted from initTabs (with tablist semantics); openFilterMenu extracted from the filter bar's onMenuToggle closure with focus into the open menu; keep the source ref selector mount handle and focus its filter; MetabrowserPluginHost.copyFromControl; focusRow hooks for Files, Commits, and Pulls.
