---
type: is
id: is-01kzyh1y7p65xpeb3zp5a6jwme
title: "PR #37 review D1: Document rollup truncation encodings"
kind: task
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - pr-review
  - pr-37
dependencies: []
parent_id: is-01kzyh19dnb273gz5mhw90bse3
created_at: 2026-08-13T21:39:35.796Z
updated_at: 2026-08-13T21:53:03.757Z
closed_at: 2026-08-13T21:53:03.756Z
close_reason: "Applied: api_rollup documents the distinct depth-truncation and node-budget rest encodings."
---
Design/documentation note at src/metabrowser/server.py api_rollup. Clarify that depth truncation uses children:null without a rest bucket, while node-budget truncation may return explicit children plus a rest bucket.
