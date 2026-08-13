---
type: is
id: is-01kzwkx7fnx68rfsx0d6y36w1w
title: Implement the Folder Overview registry and composer
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-12-directory-file-type-summary.md
labels:
  - frontend
dependencies:
  - type: blocks
    target: is-01kzwkxd4y4n9nmrjzv08etrpw
  - type: blocks
    target: is-01kzwkxst27f1wrrq2ktft2jmy
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T03:50:58.292Z
updated_at: 2026-08-13T03:51:17.056Z
---
Implement folder/overview_registry.js and overview.js plus the Overview manifest/view adapter. Publish mb.folderOverview from the folder plugin; validate and freeze descriptors; sort placement plus ID; reconcile keyed async resolutions; isolate resolve/mount errors and Retry; aggregate print state; gate hidden work; dispose exactly once. Tests use required, optional-null, failing, out-of-order, changed-key, same-key-update, and synthetic third panels and assert no built-in panel ID branches.
