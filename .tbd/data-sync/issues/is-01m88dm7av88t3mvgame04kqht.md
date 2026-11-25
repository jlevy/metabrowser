---
type: is
id: is-01m88dm7av88t3mvgame04kqht
title: "PR #811 A10: three comments beside constants state more than the code holds"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m88dfdf96exb192c9gb46hfz
hold: null
hold_until: null
created_at: 2026-11-25T03:57:39.545Z
updated_at: 2026-11-25T05:19:35.794Z
started_at: 2026-11-25T03:59:42.454Z
closed_at: 2026-11-25T05:19:35.643Z
close_reason: "Fixed in 837e9dadf and deba14ccd: INLINE_FOLD_MAX_LINES, _MAX_KEPT_BYTES, and WHOLE_UNITS comments restated. https://github.com/jlevy/metabrowser/pull/811#issuecomment-7153635595"
resolution: null
duplicate_of: null
---
Low. INLINE_FOLD_MAX_LINES (markdown_views.py:34-44) byte claim; _MAX_KEPT_BYTES (pull_rendered_diff.py:140-144) weight claim; WHOLE_BYTES/CHUNK_BYTES/BYTE_PX count UTF-16 code units while FULL_MAX_BYTES counts UTF-8 bytes. Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
