---
type: is
id: is-01m753pjt9azbw32mx985d7bdd
title: "PR #347 D3: a lost swap on an explicit refresh is reported as this refresh's success"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m753phnahw8439f040swe73f
created_at: 2026-11-11T10:50:45.960Z
updated_at: 2026-11-11T11:12:18.477Z
closed_at: 2026-11-11T11:12:18.476Z
close_reason: "fixed in e7aae837: served refresh that loses reports the disk stamp; served-job test"
resolution: null
duplicate_of: null
---
Severity: Low. PR #347 review D round 2 at 48660f96 (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5857531488). References: pulls.py:1052-1057, served_pull.py:389-396, tests/test_github_pull_record_swap.py:87-116.
