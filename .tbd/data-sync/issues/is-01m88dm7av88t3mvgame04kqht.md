---
type: is
id: is-01m88dm7av88t3mvgame04kqht
title: "PR #811 A10: three comments beside constants state more than the code holds"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m88dfdf96exb192c9gb46hfz
created_at: 2026-11-25T03:57:39.545Z
updated_at: 2026-11-25T03:57:39.545Z
---
Low. INLINE_FOLD_MAX_LINES (markdown_views.py:34-44) byte claim; _MAX_KEPT_BYTES (pull_rendered_diff.py:140-144) weight claim; WHOLE_BYTES/CHUNK_BYTES/BYTE_PX count UTF-16 code units while FULL_MAX_BYTES counts UTF-8 bytes. Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
