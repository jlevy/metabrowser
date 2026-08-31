---
type: is
id: is-01m1cda2sjv8sg4699t9g9yvs7
title: Author declarations for /api/file and the plugin hook envelopes
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md
labels: []
dependencies: []
parent_id: is-01m1b5mzft281epbec7m4mmca0
created_at: 2026-08-31T17:19:12.177Z
updated_at: 2026-08-31T17:19:12.177Z
---
These envelopes have no TypedDict at all. FileNode is a tree row, not the /api/file response with kind, views, and the content window. The first draft of the schema plan hid this cost behind the claim that the existing TypedDicts were already the declaration. Writing them is ordinary design work and should be scheduled as such, after the generator and the validation mechanism are proved on the Git family.
