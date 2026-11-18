---
type: is
id: is-01m7p1hjrfddg8p7vhepbvf3pm
title: "Structured viewer: YAML aliases expand unbounded in /api/plugin/structured/parsed (alias bomb)"
kind: bug
status: open
priority: 1
version: 1
labels:
  - security
  - alpha
dependencies: []
created_at: 2026-11-18T00:40:10.254Z
updated_at: 2026-11-18T00:40:10.254Z
---
Found while fixing mb-yqv2 (PR #542): builtin_plugins/structured/parser.py parses whole .yaml files with the safe loader, counts nodes and JSON-encodes the parsed tree, so it expands aliases: a 6-level 267-byte file gives node_count 672,604 (probe: .claude/worktrees/frontmatter-alias-bomb/attic/probe_structured.py). Reuse frontmatter_yaml.py's _Walk with a larger measured budget; refuse with a visible reason.
