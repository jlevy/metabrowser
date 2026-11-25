---
type: is
id: is-01m8857r797nrd4tg3yttd9fer
title: A conventional-commit prefix with a long scope, feat(pricing-policy):, is not set apart
kind: bug
status: closed
priority: 3
version: 5
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
updated_at: 2026-11-25T02:42:17.535Z
started_at: 2026-11-25T01:34:53.758Z
closed_at: 2026-11-25T02:42:17.520Z
close_reason: "Merged in #813 (2e466b25e): a title prefix counts up to 32 code points (TITLE_PREFIX_MAX_CHARS), measured against 52,066 real prefixed commit subjects (99.94% fit); the measurement is in tests/dom/title-prefix-session.js because formatters.js sits 3 bytes under the startup-script budget."
resolution: null
duplicate_of: null
---
The owner reported (2026-11-24) that a 21-code-point title prefix of the shape feat(pricing-policy): is not detected, so the title is not drawn prefix regular, rest bold. formatters.js caps a prefix at TITLE_PREFIX_MAX_CHARS = 16 code points.
