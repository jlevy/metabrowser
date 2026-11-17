---
type: is
id: is-01m7ktyfsk8d7grtp4jxevjf0z
title: "PR #496 review A7: 65 concurrent jobs exceeds every concurrency limit the brief cites"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7ktycr1m7798eaqhyky3qnr
created_at: 2026-11-17T04:06:24.306Z
updated_at: 2026-11-17T04:08:33.130Z
closed_at: 2026-11-17T04:08:33.130Z
close_reason: "Fixed in 8b4da0cb: recounted from started_at to completed_at over 2,779 job executions: a ceiling of 40, held for over an hour, the Pro plan's limit; the plan's queueing risk uses it."
resolution: null
duplicate_of: null
---
research:358-360, :613-614; plan:569-571. Recount running jobs from started_at to completed_at, or state the limit is unknown.
