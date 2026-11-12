---
type: is
id: is-01m774qx0e5bprjjzsmatmbe77
title: Audit layout shift on page renders; per-section layout spec for page headers
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m774qzdxvfrwsyzmx5dgtce1
  - type: blocks
    target: is-01m774r7k4mqvs813sjppzvceh
  - type: blocks
    target: is-01m77616mh9yfzy5cq7daccafn
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-12T05:47:26.605Z
updated_at: 2026-11-12T06:10:57.649Z
started_at: 2026-11-12T05:48:41.637Z
closed_at: 2026-11-12T06:10:57.647Z
close_reason: "Audit recorded in the research doc (Page Headers, Section by Section) on PR #364 at 81b4d2b1; fixes are mb-4z69, mb-6chh, mb-gsa0."
resolution: null
duplicate_of: null
---
Measure every header and metadata section of the PR page (cold landing, PR to PR across PR shapes, tabs, history, list) and the file, folder, and commit headers. Record each shift with cause and a per-section layout rule; add to the research doc.
