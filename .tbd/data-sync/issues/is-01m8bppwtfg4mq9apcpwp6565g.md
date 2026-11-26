---
type: is
id: is-01m8bppwtfg4mq9apcpwp6565g
title: "Cut the Markdown projection's cost: repeated HTML parses and whole-document renders"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-26T10:34:07.565Z
updated_at: 2026-11-26T10:34:07.565Z
---
Measured for mb-1jp0: docs/plugins.md (85 KB a side) projects in 237-317 ms in process at load 337 and 600-950 ms in the child under a cold page's other traffic. Each side is rendered whole; about half the time is html.parser, six parses a side across KPress's sanitizer, inert_html.harden, and markdown_projection._hardened; most of the rest is markdown-it. Profile script: attic/rendered-latency/profile_projection.py in the main checkout.
