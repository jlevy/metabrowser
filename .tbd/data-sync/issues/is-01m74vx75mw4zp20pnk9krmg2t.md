---
type: is
id: is-01m74vx75mw4zp20pnk9krmg2t
title: "PR #347 A2: pull record compare-and-swap discards a refresh's fresh data and defeats the documented metadata merge"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74vwmegp0f11eb7vj9pnq0t
created_at: 2026-11-11T08:34:34.803Z
updated_at: 2026-11-11T09:41:50.425Z
closed_at: 2026-11-11T09:41:50.424Z
close_reason: "fixed in ecdaaa51: checkout refresh merges against the latest record; mirror refresh that loses adopts the winner without a success stamp; tests in test_github_pull_publication.py"
resolution: null
duplicate_of: null
---
Severity: Medium. PR #347 review A round 1 at 8dd80d0c (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5855504972). References: builtin_plugins/github/pull_record.py:516-519, pulls.py:948-966, pulls.py:1060.
