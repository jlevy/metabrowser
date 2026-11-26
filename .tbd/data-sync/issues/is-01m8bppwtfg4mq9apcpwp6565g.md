---
type: is
id: is-01m8bppwtfg4mq9apcpwp6565g
title: "Cut the Markdown projection's cost: repeated HTML parses and whole-document renders"
kind: task
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m8cfgb7tygn471x857dgjzpb
hold: null
hold_until: null
created_at: 2026-11-26T10:34:07.565Z
updated_at: 2026-11-26T17:47:33.768Z
started_at: 2026-11-26T17:26:42.890Z
---
Measured for mb-1jp0: docs/plugins.md (85 KB a side) projects in 237-317 ms in process at load 337 and 600-950 ms in the child under a cold page's other traffic. Each side is rendered whole; about half the time is html.parser, six parses a side across KPress's sanitizer, inert_html.harden, and markdown_projection._hardened; most of the rest is markdown-it. Profile script: attic/rendered-latency/profile_projection.py in the main checkout.
