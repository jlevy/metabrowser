---
type: is
id: is-01kyxrjm4mvts4zh6cgp89tx5v
title: "PR #19 review R2: anchor syntax CSS blocks precisely"
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kyxrj3k0zm0d52vvjhnp4zzp
created_at: 2026-08-01T04:16:06.291Z
updated_at: 2026-08-01T04:21:00.299Z
---
R2 Low at tests/test_syntax_palette.py:114: _css_block(css, ":root") first matches a header comment. Anchor theme selectors on their complete rule openers and keep parsing failures accurate.
