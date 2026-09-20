---
type: is
id: is-01m2yskht3gqryzdb2bhn4g5zx
title: "PR 216 R4: use explicit source kind for browser path decoding and links"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2yryd6had8zdvj8eag4a4v4
hold: null
hold_until: null
created_at: 2026-09-20T06:56:06.978Z
updated_at: 2026-09-20T07:15:21.325Z
started_at: 2026-09-20T06:57:40.774Z
closed_at: 2026-09-20T07:15:21.324Z
close_reason: "Fixed in bc8dd72b: displayPath and Markdown/wiki resolvers require an explicit git_revision source kind."
resolution: null
duplicate_of: null
---
navigation.displayPath and Markdown/wiki resolvers infer Git identity from g1-* filename shape. Legal filesystem names are decoded or their authored links are encoded incorrectly. Carry explicit source kind from shell/SDK to pure resolvers and cover both source types using identical names.
