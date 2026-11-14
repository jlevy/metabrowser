---
type: is
id: is-01m1cda2sjv8sg4699t9g9yvs7
title: Author declarations for /api/file and the plugin hook envelopes
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md
labels: []
dependencies: []
parent_id: is-01m1b5mzft281epbec7m4mmca0
created_at: 2026-08-31T17:19:12.177Z
updated_at: 2026-11-14T18:44:06.312Z
---
Phase 4 of the plan. /api/file has no TypedDict: FileNode is a tree row, not the response with kind, views, and the content window. Most built-in plugin data hooks have none either; the GitHub plugin's routes already declare TypedDict envelopes (for example PullEnvelope in builtin_plugins/github/pull_route.py), which generate a schema with required keys. Writing the missing declarations is ordinary design work, scheduled after the generator and the validation mechanism are proved on the Git family.
