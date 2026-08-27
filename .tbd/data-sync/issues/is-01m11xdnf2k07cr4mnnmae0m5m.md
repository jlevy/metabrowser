---
type: is
id: is-01m11xdnf2k07cr4mnnmae0m5m
title: "PR #31 review R12: offline cache-hit path is also a write path"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:29:08.060Z
updated_at: 2026-08-27T15:44:29.644Z
closed_at: 2026-08-27T15:44:29.643Z
close_reason: "Fixed in dbe3206: failed state.yml write is non-fatal and logged; added to Phase 1B acceptance and CLI goldens as read-only application home."
resolution: null
duplicate_of: null
---
plan-2026-08-11-open-repo-from-git-url.md:379. state.yml last_opened_at is written on every open; no statement that a failed write is non-fatal.
