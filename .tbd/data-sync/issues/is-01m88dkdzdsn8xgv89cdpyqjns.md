---
type: is
id: is-01m88dkdzdsn8xgv89cdpyqjns
title: "PR #811 A7: a failed Full upgrade overrides a choice made while it was in flight"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m88dfdf96exb192c9gb46hfz
created_at: 2026-11-25T03:57:13.573Z
updated_at: 2026-11-25T03:57:13.573Z
---
Low. diff-markdown.js askFull catch 1270-1276 sets file.mode back even when the reader chose another view meanwhile; fall back only while file.mode is full. Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
