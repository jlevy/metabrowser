---
type: is
id: is-01m6mp811vf52jmazawykb3bw6
title: Make PR and Git navigation feel immediate with measured prefetching
kind: feature
status: in_progress
priority: 1
version: 24
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
  - is-01m6mzhaqwfp2frzwkpyjh7p62
  - is-01m6n17whe9tnqh95c7j5560rr
  - is-01m6n43mfv1y88nsemyc2y3tqq
  - is-01m6n43xgpc5a5py8rt60gjma8
  - is-01m6n5xwntvy5fmqtrewb5kp9z
  - is-01m6n96gp3d4kaba25mk0nrbbq
  - is-01m6ng3rk55p8sm1970bqkvqmv
hold: null
hold_until: null
created_at: 2026-11-05T01:47:46.617Z
updated_at: 2026-11-05T18:49:22.392Z
started_at: 2026-11-05T01:47:47.197Z
---
Improve perceived navigation latency for pull-request selection and Git history on a new branch from verified main. Follow the existing performance-loop framework: register a few falsifiable hypotheses before implementation; test their mechanisms on the unchanged build; use frozen subjects and explicit cold, warm, prepared and unprepared cache states; measure trusted input to exact useful painted content, including server, decode, asset and mount phases. Confirm accepted changes with interleaved repeated controls and candidate runs, preserve correctness/cancellation/account/source ownership and bounded background work, and record rejected hypotheses as well. Reuse existing harnesses and concise session/golden tests rather than adding a parallel framework. Preserve the default installed verified build and the two user preview servers while experimenting; install a successor only after verification. Track actual timings, ranges, bytes, request counts/concurrency, long tasks, CPU/RSS and cache provenance. Branch: codex/perf-prefetch-20261104. No speculative product changes before diagnostic evidence.

## Notes

First performance layer: PR #299, 0d1b132d on main base db52ec09. Independent review clean, full local verification and normal push gate passed. GitHub CI is running. The bounded visible-PR preparation remains a separate measured experiment (mb-oywk).

PR #299 is mergeable and all nine GitHub CI jobs passed, including admitted Git 2.43 and 2.50. First-layer beads closed. H74/H75 broader diagnostics and the visible preparation experiment remain open.

Confirmed two more layers using the existing hypothesis, paired measurement, and unchanged gate workflow: selected settlement (mb-dmby, exp-051), then bounded visible descriptions (mb-oywk, exp-052). H81 depends on H82. Both manually verified in existing checkout and URL-managed mode, with repository verification running. Default CLI remains verified main.

Exact full gate passed for 1a39e43b stacked above 034d1491 and PR #299. The two additional layers are in the ordinary atomic pre-push gate; native stack linking and exact CI remain.

Native stack #302 fully verified and ready for owner merge: #299 0d1b132d, #300 034d1491, #301 3c8acd21. All three clean, non-draft, and 9/9 green. First-layer Qodo dispositions published, and all four top-layer findings fixed/resolved with review evidence. H81/H82/H83 scoped beads closed. Default installed CLI remains verified main. Broader H74/H75 diagnostic beads remain open.

Installation and review follow-up: both default CLI entry points now run the verified stack-tip wheel 0.11.1.dev1162+3c8acd21. The installed doctor passed all 11 plugin checks and the older preview processes were stopped. GitHub still shows the same three heads in native stack #302, each mergeable with all nine checks green. The remaining #299 thread has a recorded rebuttal and awaits reviewer closure. The stack awaits owner merge. The H74 and H75 measurements are open follow-ups outside this delivery.
