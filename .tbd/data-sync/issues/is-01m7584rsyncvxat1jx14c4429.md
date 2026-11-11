---
type: is
id: is-01m7584rsyncvxat1jx14c4429
title: "PR #347 E3: a lost swap still reports the winner's success, and a race caches the winner's previous stamp"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7584qkw8sr4z3rn6rhd610h
created_at: 2026-11-11T12:08:25.149Z
updated_at: 2026-11-11T12:27:05.191Z
closed_at: 2026-11-11T12:27:05.190Z
close_reason: "fixed in e62e2b6b: served job reads the shared stamp from disk after a lost swap via last_refresh; two race tests"
resolution: null
duplicate_of: null
---
Severity: Low. PR #347 review E round 3 at 86261188 (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5858411904). References: pulls.py:1070-1071, served_pull.py:389-405, :464-475, pull_route.py:405.
