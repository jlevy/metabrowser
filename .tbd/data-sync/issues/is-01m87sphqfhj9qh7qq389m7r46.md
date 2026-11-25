---
type: is
id: is-01m87sphqfhj9qh7qq389m7r46
title: Bound the structured Tree view's YAML and JSONC parsing
kind: bug
status: open
priority: 2
version: 2
spec_path: docs/project/architecture/arch-threat-model.md
labels:
  - security
dependencies: []
parent_id: is-01m8898kcprj50strs0xfshvjn
created_at: 2026-11-24T22:09:24.206Z
updated_at: 2026-11-25T02:44:17.600Z
---
Threat model T7. builtin_plugins/structured/parser.py parses YAML (ruamel safe, then PyYAML) and JSONC (json5) under only the 8 MiB STRUCTURED_PARSE_MAX_BYTES input cap: alias expansion, recursion in _count_nodes_and_depth, and re-serialization are unbounded, unlike front matter's bounded loader (frontmatter_yaml.py). Route it through the bounded loader or a child with a deadline; add an alias-bomb test.
