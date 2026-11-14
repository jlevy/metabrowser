---
type: is
id: is-01m1b5n1awje3r2enbetszw8kx
title: Validate the Git golden envelopes against the strict generated schema
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md
labels: []
dependencies:
  - type: blocks
    target: is-01m1b5n0zs32tdr8rhy1x6wzjc
parent_id: is-01m1b5mzft281epbec7m4mmca0
created_at: 2026-08-31T05:46:08.091Z
updated_at: 2026-11-14T18:46:27.145Z
---
Phase 2 of the plan. Validate the envelopes in cli-api-git.tryscript.md against the strict schema variant from mb-t8py. A transcript holds a real captured response, so checking it proves the schema describes what the server sends rather than what someone believed it sent. Transcripts are normalized (placeholders change types and elisions sit inside JSON strings), so state how validation works, most likely by capturing the pre-normalization envelope in the harness rather than parsing the transcript back. If that cannot be made to work, stop and reconsider the plan: the route (mb-t8n3) and every later phase depend on it. Ordered before the route deliberately, because a schema nothing checks is a second description that can drift from the first.
