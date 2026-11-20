---
type: is
id: is-01m7n8ardt2zyqya7j20f7w9ja
title: "PR view and Pulls: hunt a performance regression against v0.12.0 and recent main"
kind: task
status: closed
priority: 1
version: 5
delegate: claude-code@spud10.local
labels:
  - linear
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
hold: null
hold_until: null
created_at: 2026-11-17T17:19:32.281Z
updated_at: 2026-11-20T17:00:23.700Z
started_at: 2026-11-17T17:21:36.436Z
closed_at: 2026-11-20T17:00:23.696Z
close_reason: "Done: the regression step was found (#369's first-paint hold), the repeatable benchmark and exp-099 merged in #524, exp-100 in #525, and the fix (header painted at once) in #526"
resolution: null
duplicate_of: null
---
The owner finds it a little slower since recent PRs. Benchmark the PR view against v0.12.0 and main from a few days ago, bisect a step change, and name the commit. Keep a durable, repeatable benchmark in explorations/performance-loop covering (1) route and git/gh time behind the diff summaries, cold and warm cache, and (2) time to display in a real browser (first paint of the loading box and of the summary, time to complete), back-to-back pairs per the tolerance policy.

## Notes

Found 2026-11-17 (3 back-to-back pairs per comparison, 1.3x rough cut, load 5-13): the step is #369 (597a7c70e, 2026-11-13), its conversation first-paint hold (DESCRIPTION_HOLD_MS 200, holdFirstPaint in pull-page.js): on a cached PR (#487, 4 texts on the first screen) the title waits for every first-screen Markdown, 2 at a time. pr-warm title 683 ms (v0.12.0) vs 961 ms (main), pairs 1.33/1.58/1.38; across #369 a warm reload's title 112 -> 204 ms (3/3 beyond). v0.12.0 vs main of Nov 12: no difference. Cold-record path and Pulls rows unchanged. Fix options: (1) paint the header at once, hold only the body - undoes cf117163a's change-once rule, owner's call; (2) request the held Markdown all at once (saves a round trip, 50-80 ms on a fresh server); (3) warm KPress and route modules at startup (older 350-500 ms first GET pull). Benchmark (pr-view*.mjs/sh, protocol) saved in the side-session notes folder pr-view-benchmark/ and clever-joliot-058250/attic/pr-view-benchmark/; full report regression-hunt-report.md there.
