---
type: is
id: is-01m09s72hhtrzyr71j0dhwwwfj
title: "Diff: decide the core/plugin split for hosted and document sources"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-18T06:33:51.408Z
updated_at: 2026-08-18T06:33:51.408Z
---
The spec puts the comparison model and renderer in core and keeps sources as adapters: Git in core beside git/, hosted providers as plugins because a provider is a consumer domain. A GitHub adapter needs several Platform A1-A5 items that the core decision otherwise defers. Settle which of those the first external adapter actually requires, so they are scheduled against a real consumer rather than speculatively.
