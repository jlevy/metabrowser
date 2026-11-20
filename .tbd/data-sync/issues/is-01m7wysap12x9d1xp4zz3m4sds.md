---
type: is
id: is-01m7wysap12x9d1xp4zz3m4sds
title: Event log and observability
kind: epic
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-19-structured-event-log.md
labels: []
dependencies: []
child_order_hints:
  - is-01m7vsaw74j5kjh877686npatq
  - is-01m7vsaz137bzapm5p4jbjp04d
  - is-01m7vcsybx3csjxfbe7jans41w
  - is-01m7vcsytb7waf0fmz06bhjxwb
  - is-01m7h0xjthfz5t19t0sydzgvpj
  - is-01m7ts09te3ty0ca6tbbsybgrj
created_at: 2026-11-20T17:06:39.418Z
updated_at: 2026-11-20T17:11:56.693Z
---
Metabrowser keeps a structured JSON event log of requests, background jobs and subprocesses (#618), names the cause of every failed GitHub call (#620), reports slow requests, freezes and late waits from the page (#629), and browses its own log in Metabrowser (#633, #634). Plan: docs/project/specs/active/plan-2026-11-19-structured-event-log.md.

What remains: the reporter's late paths and the requests in flight before it installs (mb-fqy1, mb-nhf2), the Timeline's name, client and cause chips (mb-7uqr), measuring open-to-first-row for the log views and skipping the generic JSONL envelope for hook-backed kinds (mb-9n0x), and the event-loop lag sampler (mb-x3x1).
