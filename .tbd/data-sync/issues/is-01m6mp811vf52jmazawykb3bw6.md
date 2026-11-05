---
type: is
id: is-01m6mp811vf52jmazawykb3bw6
title: Make PR and Git navigation feel immediate with measured prefetching
kind: feature
status: in_progress
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-prefetch
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
child_order_hints:
  - is-01m6mph0qe489751nr9gb2hfq3
  - is-01m6mpjbb70kg8tdwgznd5tdvx
  - is-01m6mpjbqxs81cdgeg8fgjgjat
  - is-01m6mr68zq45xz8wz6das0q2x6
  - is-01m6msqxnfdpdgj9d3bykq9knv
  - is-01m6mt130svbg10hxkvkt62bhx
  - is-01m6mv2e96yj34gqsra4f0prmz
  - is-01m6mwaa51n75m8kxnprppnr6n
  - is-01m6mwzwzd4jmbe0jbpxqpep3j
hold: null
hold_until: null
created_at: 2026-11-05T01:47:46.617Z
updated_at: 2026-11-05T03:45:40.332Z
started_at: 2026-11-05T01:47:47.197Z
---
Improve perceived navigation latency for pull-request selection and Git history on a new branch from verified main. Follow the existing performance-loop framework: register a few falsifiable hypotheses before implementation; test their mechanisms on the unchanged build; use frozen subjects and explicit cold, warm, prepared and unprepared cache states; measure trusted input to exact useful painted content, including server, decode, asset and mount phases. Confirm accepted changes with interleaved repeated controls and candidate runs, preserve correctness/cancellation/account/source ownership and bounded background work, and record rejected hypotheses as well. Reuse existing harnesses and concise session/golden tests rather than adding a parallel framework. Preserve the default installed verified build and the two user preview servers while experimenting; install a successor only after verification. Track actual timings, ranges, bytes, request counts/concurrency, long tasks, CPU/RSS and cache provenance. Branch: codex/perf-prefetch-20261104. No speculative product changes before diagnostic evidence.
