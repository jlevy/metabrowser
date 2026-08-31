---
type: is
id: is-01m1b5n06x1efn3vrrg79q5ge0
title: Decide whether /api/* stays an internal contract
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md
labels: []
dependencies: []
parent_id: is-01m1b5mzft281epbec7m4mmca0
created_at: 2026-08-31T05:46:06.939Z
updated_at: 2026-08-31T05:46:06.939Z
---
The map document and AGENTS.md both state that /api/ envelopes are an internal contract versioned with the shell, not a standard. Publishing OpenAPI would make them a surface others may build against, which costs the freedom to change an envelope in the same commit as the shell that reads it. The schema plan assumes the internal answer. If the answer is no, that plan is wrong and the work is instead versioned routes, a deprecation policy, and a published OpenAPI document. Blocks everything else here.
