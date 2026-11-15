---
type: is
id: is-01m774r9n7z8bymhs94yjq67sw
title: Collapse the cold landing chain
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
created_at: 2026-11-12T05:47:39.558Z
updated_at: 2026-11-15T06:55:40.887Z
closed_at: 2026-11-15T06:55:40.885Z
close_reason: "H96 amended into H118 (mb-gdmt), landing data starts with the document, per the architecture review (R7): an inline head script starts the content request, after H113's render GET and H115 (a)."
resolution: duplicate
duplicate_of: is-01m7ezsmvy8gsgc3g9d1x7dnt3
---
Concatenate startup scripts in the server, preload the kind's module graph after the startup scripts, request content early; re-measure the tree-first order. Measured as round-trip levels and cold and reload ready.
