---
type: is
id: is-01m6g6cagcckfs78k2ddzs1zz9
title: "PR #280: fix and verify system-font message measure"
kind: bug
status: in_progress
priority: 2
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
hold: null
hold_until: null
created_at: 2026-11-03T07:53:32.427Z
updated_at: 2026-11-03T09:14:12.354Z
started_at: 2026-11-03T07:55:00.843Z
---
Follow-up of996ea90d: confirmed all messages remain sans in Chrome across themes/reading fonts, but system-ui glyph advance differs from Source Sans while message width stays fixed. Resolve Qodo inline4451002801 with page-scoped dynamic measurement and regression evidence.

## Notes

Forward commit64fa6b1f is pushed on PR280. ReviewD confirmed system-ui width defect; independent ReviewE is clean (https://github.com/jlevy/metabrowser/pull/280#pullrequestreview-5749432646). Chrome8setting combinations preserve clean689.953px and measure system776.234px at actual15px; ordinary document tokens unchanged. Fullverify4180tests/301goldens plus audits/distribution/smokes and normal677spre-push passed. GitHub9checks running; close aftergreen.
