---
type: is
id: is-01m7pj8gve71bkvxyw96nqa4yn
title: "Chrome starts: retry a start cut off at START_BOUND_MS only once a warm start is seen to hang"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-18T05:32:19.181Z
updated_at: 2026-11-18T05:32:19.181Z
---
From review A on #554 (A1). launchChrome (tests/dom/chrome-session.mjs) retries only a start that exited; a start cut off at START_BOUND_MS is not retried. Why: every hang CI has shown (8 jobs in the newest 200 ci.yml runs to 44232615626) was a cold first start, and a start cut off at the bound left the next start in its job 13 to 67 s slower than warm, so a second start does not fit the 40 to 48 s session bounds of most Chrome modules and turns a 30 s 'Chrome did not start' into a 'session ran past N s' that loses the second start's record. The run's warm-up (tests/chrome_starts.py) now takes the cold start. Unblock condition: a CI run's 'chrome starts:' summary line shows a test's start (not the warm-up) cut off at START_BOUND_MS after a warm-up that answered. Then size a retry from that failure (how long the start that followed took) against the session bounds, or close this if no such line has appeared by the 0.13 release.
