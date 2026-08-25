---
type: is
id: is-01m0vdp4m0tbnfwb5zjdmt2szm
title: "PR #74 review R4: make watcher batch loss explicit"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0vcsh5mt08cfhzztanzt880
created_at: 2026-08-25T02:58:41.907Z
updated_at: 2026-08-25T02:58:41.907Z
---
PR #74 review https://github.com/jlevy/metabrowser/pull/74#issuecomment-5404472008 at head 68eeaac. R4 High. watch_backends.py:315-331 swallows refresh batch failures and continues reporting running/fresh. Ensure every observation is verified or record a typed watcher gap and stale freshness; add a middle-chunk failure test.
