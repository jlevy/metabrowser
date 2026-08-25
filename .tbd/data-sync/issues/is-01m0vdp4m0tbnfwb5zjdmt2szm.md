---
type: is
id: is-01m0vdp4m0tbnfwb5zjdmt2szm
title: "PR #74 review R4: make watcher batch loss explicit"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0vcsh5mt08cfhzztanzt880
created_at: 2026-08-25T02:58:41.907Z
updated_at: 2026-08-25T04:46:34.599Z
closed_at: 2026-08-25T04:46:34.598Z
close_reason: R4 resolved and verified by make verify.
resolution: null
duplicate_of: null
---
PR #74 review https://github.com/jlevy/metabrowser/pull/74#issuecomment-5404472008 at head 68eeaac. R4 High. watch_backends.py:315-331 swallows refresh batch failures and continues reporting running/fresh. Ensure every observation is verified or record a typed watcher gap and stale freshness; add a middle-chunk failure test.

## Notes

Watcher batches are normalized and sent in contract-sized chunks; incomplete, rejected, or failed chunks stop observation and publish failed watcher status so provider freshness becomes stale with watcher_gap. Tests cover refresh exception, rejected receipt, and a failure in the middle of three chunks. Required aggregate-repair failures also transition discovery to failed instead of logging and claiming done.
