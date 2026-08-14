---
type: is
id: is-01kzzac0dhshh0qxt70dp5mbnp
title: "PR #40 review R1: prevent empty File type presets"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kzzabe6f9r3fwtbd3w4tddqy
created_at: 2026-08-14T05:02:00.110Z
updated_at: 2026-08-14T05:25:15.409Z
closed_at: 2026-08-14T05:25:15.408Z
close_reason: "Fixed: empty presets are omitted and zero-member presets cannot match the empty selection."
---
PR #40 comment 5289663054, R1. file_type_filters.py and filter_controls.js: an empty Other preset vacuously matches an empty selection, labels the chip Other, and renders a no-op menu row. Remove empty presets and harden the control; add regressions.
