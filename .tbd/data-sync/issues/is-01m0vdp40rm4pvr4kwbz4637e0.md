---
type: is
id: is-01m0vdp40rm4pvr4kwbz4637e0
title: "PR #74 review R3: make snapshot and live handoff atomic"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0vcsh5mt08cfhzztanzt880
created_at: 2026-08-25T02:58:41.302Z
updated_at: 2026-08-25T02:58:41.302Z
---
PR #74 review https://github.com/jlevy/metabrowser/pull/74#issuecomment-5404472008 at head 68eeaac. R3 High. events_route.py:587-615 attaches before an unversioned snapshot and can replay covered older deltas after it. Add a coherent snapshot plus HostCursor handoff and forced delete/recreate interleaving tests.
