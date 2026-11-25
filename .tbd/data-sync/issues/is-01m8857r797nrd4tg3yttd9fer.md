---
type: is
id: is-01m8857r797nrd4tg3yttd9fer
title: A conventional-commit prefix with a long scope, feat(pricing-policy):, is not set apart
kind: bug
status: in_progress
priority: 3
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/813
    at: 2026-11-25T02:38:30.155Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-25T01:31:02.245Z
updated_at: 2026-11-25T02:38:30.173Z
started_at: 2026-11-25T01:34:53.758Z
---
The owner reported (2026-11-24) that a 21-code-point title prefix of the shape feat(pricing-policy): is not detected, so the title is not drawn prefix regular, rest bold. formatters.js caps a prefix at TITLE_PREFIX_MAX_CHARS = 16 code points.
