---
type: is
id: is-01m6kc1q2z4b9wrmt6qb90t0vj
title: Guard progressive PR file-list publication against GitHub account changes
kind: bug
status: in_progress
priority: 1
version: 4
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6jhctf78vq1v7ndv43jzssy
parent_id: is-01m6jhct45pr1qjep5v3ea0a69
hold: null
hold_until: null
created_at: 2026-11-04T13:30:19.614Z
updated_at: 2026-11-04T14:58:12.838Z
started_at: 2026-11-04T13:48:45.641Z
---
Confirmed postlanding Medium correctness/account-provenance finding on actual main da87bb13. pull_files_refresh.py publishes progressive REST prefixes using the initially captured login before its final active-account check. Controlled unchanged-production probe shows switch before page1 leaves B-owned rows persisted under gh:A after final account_changed; switching before page2 then failing page3 bypasses the final check and normal GET reports current readerA with mixed A+B rows plus network_error. Stable-account success/failure controls pass. Add the smallest existing account guard before each progressive publication and retain final-publication checking; preserve generation, admitted-cache/refusal/backoff semantics, Git-local no-provider path and progressive valid prefixes. No token wrapper, real account switch or new abstraction. Independently recheck the unchanged controlled probe, focused production tests, auth-call cost and normal gates; land a reviewed forward fix before final documentation/installed-build completion.

## Notes

2026-11-04: Forward correction https://github.com/jlevy/metabrowser/pull/297 merged normally at afaf38b85a83443e25002765203c216bd11f8dfa. Its whole tree equals the reviewed cc93c132 candidate. Full make verify passed (4,786 Python tests, 9 expected skips, 378 session golden commands), normal pre-push gate passed, and all nine exact-head PR CI jobs passed. Independent security/correctness and performance reviews are on the PR. The exact noneditable wheel passed eight public live and six installed regression cases. Actual-main CI and independent integration reconciliation remain pending; this bead stays in progress until those finish.
