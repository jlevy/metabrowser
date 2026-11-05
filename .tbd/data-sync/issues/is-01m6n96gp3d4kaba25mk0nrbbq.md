---
type: is
id: is-01m6n96gp3d4kaba25mk0nrbbq
title: Measure selected PR settlement without the one-second poll boundary
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-prefetch
labels: []
dependencies:
  - type: blocks
    target: is-01m6mwzwzd4jmbe0jbpxqpep3j
parent_id: is-01m6mp811vf52jmazawykb3bw6
created_at: 2026-11-05T07:19:00.034Z
updated_at: 2026-11-05T08:19:42.569Z
---
H82 / exp-051 hypothesis. In two immediate clicks with no speculative gh subprocess, complete records published about 0.15 s after the three-second GET and Conversation waited until the next poll. Isolate one bounded selected cache read that waits for its already-running refresh to settle, with one waiter, prompt cancellation and no provider side effects. Record provider publication and UI paint separately, first with deterministic session control, then exact installed pairs. Keep H81 trial failures and no speculative work overlap observations; do not interpret provider jitter as an application speed claim.

## Notes

Backend and browser sessions reproduced the missed settlement and timeout scheduling errors; 26 combined focused cases and nine related goldens passed. Five installed H82-only pairs reduced publication-to-paint from 166–965 ms to 26–105 ms; strict directory performance gate passed. Independent review found a held request must recheck its pin after a concurrent switch. The final artifact requires that regression test and a fresh timing confirmation.

Final pin-safe H82 accepted in exp-051. Three exact pairs reduced local publication-to-full paint from 73–852 ms to 26–29 ms. Final strict directory gate passed. A real pin switch yielded typed 409 for the original claim and an ordinary unclaimed read succeeded. Built-in browser verified checkout and managed URL. Branch codex/perf-pr-settlement-20261104 at e5baf2fb; stacked verification running.
