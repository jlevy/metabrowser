---
type: is
id: is-01m0vdp3f658v4apshehjtk2mf
title: "PR #74 review R2: align file budget and lossless paging"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0vcsh5mt08cfhzztanzt880
created_at: 2026-08-25T02:58:40.740Z
updated_at: 2026-08-25T03:05:51.916Z
---
PR #74 review https://github.com/jlevy/metabrowser/pull/74#issuecomment-5404472008 at head 68eeaac. R2 High. InventoryConfig.max_entries is passed to the legacy max_files cap; directory-heavy roots can exceed it, while events_route.py:287-309 ignores DirectoryProjection continuation. Align budget semantics with max_files or a true entry cap and make complete consumers losslessly assemble pages.
