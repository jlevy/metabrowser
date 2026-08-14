---
type: is
id: is-01kzzac1fqy4pa8f1bsg0x2g3x
title: "PR #40 review R5: centralize group routing and support all registry groups"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzzabe6f9r3fwtbd3w4tddqy
created_at: 2026-08-14T05:02:01.207Z
updated_at: 2026-08-14T05:25:16.843Z
closed_at: 2026-08-14T05:25:16.842Z
close_reason: "Fixed: every kind now resolves an authoritative group_id in Registry v1; family-less kinds declare group and Python/JavaScript consumers no longer infer it."
---
PR #40 comment 5289663054, R5. Family-less kinds cannot route to logs/archives/media; group extras can KeyError if registry groups change; content-to-group logic is duplicated across Python and JS. Centralize exported routing and validate it.
