---
type: is
id: is-01m7p1hjrfddg8p7vhepbvf3pm
title: "Structured viewer: YAML aliases expand unbounded in /api/plugin/structured/parsed (alias bomb)"
kind: bug
status: in_progress
priority: 1
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/928
    at: 2026-11-28T18:10:09.705Z
delegate: codex@spud10.local
labels:
  - security
  - alpha
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
hold: null
hold_until: null
created_at: 2026-11-18T00:40:10.254Z
updated_at: 2026-11-28T18:10:09.719Z
started_at: 2026-11-28T17:49:40.839Z
---
Found while fixing mb-yqv2 (PR #542): builtin_plugins/structured/parser.py parses whole .yaml files with the safe loader, counts nodes and JSON-encodes the parsed tree, so it expands aliases: a 6-level 267-byte file gives node_count 672,604 (probe: .claude/worktrees/frontmatter-alias-bomb/attic/probe_structured.py). Reuse frontmatter_yaml.py's _Walk with a larger measured budget; refuse with a visible reason.

## Notes

2026-11-18 from PR #542 addressing: reuse frontmatter_yaml.load_bounded_yaml via a short multi-document variant (override get_data so each document is measured on the composed graph before construction, under a shared budget, plus its own byte bound). Reusing _Walk alone does not bound it (review B). The JSON-safe copy changes rendering: non-string keys become their JSON text. The PyYAML fallback can likely go, ruamel being a hard dependency.
