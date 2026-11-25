---
type: is
id: is-01m8857r797nrd4tg3yttd9fer
title: A conventional-commit prefix with a long scope, feat(trading-policy):, is not set apart
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
created_at: 2026-11-25T01:31:02.245Z
updated_at: 2026-11-25T01:31:02.245Z
---
The owner reported (2026-11-24) that the title prefix feat(trading-policy): is not detected, so the title is not drawn prefix regular, rest bold. formatters.js caps a prefix at TITLE_PREFIX_MAX_CHARS = 16 code points, and this one is 21.
