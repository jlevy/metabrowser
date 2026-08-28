---
type: is
id: is-01m0jswn4dgygrcgnzz5g2mbtj
title: "metab --show <path>: the four layers for one selection"
kind: feature
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0jsxesr35r0d8rkrar80nex
  - type: blocks
    target: is-01m0jsxgfznxwn8cwr2n3p01f4
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:38:48.461Z
updated_at: 2026-08-28T07:09:44.158Z
closed_at: 2026-08-28T07:09:44.155Z
close_reason: metab --show PATH reports route, kind, views, and model summary in text or JSON, built on /api/file and format_view_href. Pinned by tests/golden/cli-show.tryscript.md across all eight built-in kinds.
resolution: null
duplicate_of: null
---
Reports the route a path resolves to, the kind it classifies as, the views it offers, and a summary of its model. The single most valuable missing command: /api/file decides which tabs a reader sees, and nothing outside a browser currently proves that README.md opens as markdown with Document and Source. Ships with cli-show.tryscript.md over a fixture carrying one file of each built-in kind.
