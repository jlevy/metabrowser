---
type: is
id: is-01m402f17fzfw3tac1d4vfxxe4
title: Remove the Tryscript braces advisory blocker without weakening audits
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
hold: null
hold_until: null
created_at: 2026-10-03T05:05:52.366Z
updated_at: 2026-10-05T04:43:11.843Z
started_at: 2026-10-05T04:43:11.828Z
---
Main CI run 37098062964 fails npm audit for GHSA-vfj7-8cjw-p6xm. Chain: tryscript 0.1.7 -> fast-glob -> micromatch -> braces. Latest published tryscript 0.2.1 and upstream main still use fast-glob; advisory lists no patched braces. Prepare a reviewed upstream removal or replacement, adopt a published fixed release under supply-chain policy, and rerun all CLI goldens and audits. Upstream implementation approval was requested in chat; publishing requires separate authorization.
