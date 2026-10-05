---
type: is
id: is-01m402f17fzfw3tac1d4vfxxe4
title: Remove the Tryscript braces advisory blocker without weakening audits
kind: bug
status: closed
priority: 1
version: 4
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
hold: null
hold_until: null
created_at: 2026-10-03T05:05:52.366Z
updated_at: 2026-10-05T05:29:24.020Z
started_at: 2026-10-05T04:43:11.828Z
closed_at: 2026-10-05T05:29:24.006Z
close_reason: "Fixed in PR268 commit f67606b7. Full make verify passed: 4006 pytest tests, 8 live-test skips, 278 goldens, clean npm/Python audits and distribution checks. All nine GitHub checks passed in run 37267339978; review posted on PR268."
resolution: null
duplicate_of: null
---
Main CI run 37098062964 fails npm audit for GHSA-vfj7-8cjw-p6xm. Chain: tryscript 0.1.7 -> fast-glob -> micromatch -> braces. Latest published tryscript 0.2.1 and upstream main still use fast-glob; advisory lists no patched braces. Prepare a reviewed upstream removal or replacement, adopt a published fixed release under supply-chain policy, and rerun all CLI goldens and audits. Upstream implementation approval was requested in chat; publishing requires separate authorization.

## Notes

Fix prepared for PR 268: exact Tryscript 0.3.0 pin replaces fast-glob with tinyglobby and removes micromatch/braces. Registry integrity matched lockfile; newly added third-party versions all exceed the 14-day cool-off. First-party artifact selected explicitly while leaving transitive min-release-age and disabled lifecycle scripts intact. npm audit reports 0 vulnerabilities. Direct golden replay found a separate HOME/config isolation issue (mb-hf20), fixed without updating expected output; isolated transcript passes 19 cases. Full make verify and final CI pending.
