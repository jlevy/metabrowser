---
type: is
id: is-01m774r9n7z8bymhs94yjq67sw
title: "H96: concatenated startup scripts, after U2 (its early content request moved to H118)"
kind: task
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:39.558Z
updated_at: 2026-11-15T07:26:28.977Z
closed_at: null
close_reason: null
resolution: null
duplicate_of: null
---
Concatenate startup scripts in the server, preload the kind's module graph after the startup scripts, request content early; re-measure the tree-first order. Measured as round-trip levels and cold and reload ready.

## Notes

Reopened: Re-review of #441 (2026-11-15): folding H96 into H118 dropped H96's concatenated startup scripts, which H26's remote request-count fix relies on. H96 keeps that half, ordered after U2 (mb-cejc) and judged remotely with H44's regime; the early content request stays in H118 (mb-gdmt).
