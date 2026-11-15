---
type: is
id: is-01m774rbhb56bd9d69fq1y3f0c
title: One layout per Markdown mount
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:41.482Z
updated_at: 2026-11-15T06:55:39.725Z
closed_at: 2026-11-15T06:55:39.724Z
close_reason: "H100 merged on 2026-11-14 into H112 (mb-wki1), one surface store, per the architecture review (R1): one kept host per subject replaces the separate retention tiers, and H112 records a lettered verdict for this mechanism. Its decider, layout passes per mount 2 → 1, is H112 (a)."
resolution: duplicate
duplicate_of: is-01m7ezshzwvgr17jz8fkawd3hz
---
Defer the table of contents scroll read until after the swap, or commit without re-parenting. Measured as layout passes over 10 ms and painted-ready.
