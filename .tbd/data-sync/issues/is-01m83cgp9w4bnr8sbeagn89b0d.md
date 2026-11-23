---
type: is
id: is-01m83cgp9w4bnr8sbeagn89b0d
title: "PR #724 A3: after a failed first rollup the map stays hidden even when Retry succeeds"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m836s55277yzehg502zen0ra
created_at: 2026-11-23T05:02:03.066Z
updated_at: 2026-11-23T05:02:05.325Z
closed_at: 2026-11-23T05:02:05.323Z
close_reason: "fixed: in `1c4d0d59b`: the breakdown's Retry calls the map's `refresh()` and its answers reach `follow()`; session steps for both a failed breakdown and a failed map rollup, each recovering on Retry"
resolution: null
duplicate_of: null
---
Review A on https://github.com/jlevy/metabrowser/pull/724, finding A3 (Medium): after a failed first rollup the map stays hidden even when Retry succeeds.
