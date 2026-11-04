---
type: is
id: is-01m6kc1q2z4b9wrmt6qb90t0vj
title: Guard progressive PR file-list publication against GitHub account changes
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhct45pr1qjep5v3ea0a69
created_at: 2026-11-04T13:30:19.614Z
updated_at: 2026-11-04T13:30:19.614Z
---
Confirmed postlanding Medium correctness/account-provenance finding on actual main da87bb13. pull_files_refresh.py publishes progressive REST prefixes using the initially captured login before its final active-account check. Controlled unchanged-production probe shows switch before page1 leaves B-owned rows persisted under gh:A after final account_changed; switching before page2 then failing page3 bypasses the final check and normal GET reports current readerA with mixed A+B rows plus network_error. Stable-account success/failure controls pass. Add the smallest existing account guard before each progressive publication and retain final-publication checking; preserve generation, admitted-cache/refusal/backoff semantics, Git-local no-provider path and progressive valid prefixes. No token wrapper, real account switch or new abstraction. Independently recheck the unchanged controlled probe, focused production tests, auth-call cost and normal gates; land a reviewed forward fix before final documentation/installed-build completion.
