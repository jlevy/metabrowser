---
type: is
id: is-01m774r967jvcvcx4btkpyfzeg
title: Per-main-tab retained surfaces
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:39.078Z
updated_at: 2026-11-15T06:55:38.963Z
closed_at: 2026-11-15T06:55:38.962Z
close_reason: "H95 merged on 2026-11-14 into H112 (mb-wki1), one surface store, per the architecture review (R1): one kept host per subject replaces the separate retention tiers, and H112 records a lettered verdict for this mechanism."
resolution: duplicate
duplicate_of: is-01m7ezshzwvgr17jz8fkawd3hz
---
Files, Commits, and Pulls each keep their own surface; a switch suspends instead of claiming the pane. Measured as main-tab switch painted-ready, blank frames, requests.
