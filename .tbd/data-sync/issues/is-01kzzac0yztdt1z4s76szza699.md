---
type: is
id: is-01kzzac0yztdt1z4s76szza699
title: "PR #40 review R3: remove unreachable browser taxonomy compatibility payload"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzzabe6f9r3fwtbd3w4tddqy
created_at: 2026-08-14T05:02:00.670Z
updated_at: 2026-08-14T05:25:16.127Z
closed_at: 2026-08-14T05:25:16.126Z
close_reason: "Fixed: removed the unreachable client taxonomy projection and legacy browser fallback; the page embeds one authoritative Registry v1 payload while public SDK and wire aliases remain compatible."
---
PR #40 comment 5289663054, R3. Review and remove unreachable mixed-version browser fallback data and guards while preserving real SDK aliases for one supported cycle; avoid duplicated inline registry/taxonomy payloads.
