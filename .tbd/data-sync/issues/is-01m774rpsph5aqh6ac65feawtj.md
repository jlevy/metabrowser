---
type: is
id: is-01m774rpsph5aqh6ac65feawtj
title: "Registry: Shift rule, modifier rejection, digit precedence, targets"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rq85ps5fkhed4te4nhq4
  - type: blocks
    target: is-01m774rrky1bpnkwshfqy4vqrz
  - type: blocks
    target: is-01m774rtafehnx278pq5a90vgq
parent_id: is-01m76jgfxbadse383jypkzwpm9
created_at: 2026-11-12T05:47:53.013Z
updated_at: 2026-11-12T05:47:56.621Z
---
Design > Shift Rule Matching and Badge Targets. Key classes with fixed Shift policy; reject a Shift policy on character bindings and any required Ctrl/Alt/Meta; digit match by event.key then event.code; describeKey/appendKey; view-tabs, controls, filters groups; dispatch event; plugin scope below global; reveal surface; attachTarget with dispatch-time liveness (connected, visible, not disabled, not inert) and immediate badges during a reveal.
