---
type: is
id: is-01m8e62rnz7kjmqh43dywxvkae
title: Repair full verification regressions for collection folder tables
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwhv15ckjw7prckfmmggr
hold: null
hold_until: null
created_at: 2026-11-27T09:41:13.971Z
updated_at: 2026-11-27T09:51:14.822Z
started_at: 2026-11-27T09:42:31.403Z
closed_at: 2026-11-27T09:51:14.773Z
close_reason: Committed and validated focused regressions; isolated host/environment failures, with full stack CI gate handed to parent under mb-r7zc.
resolution: null
duplicate_of: null
---
Diagnose the incomplete make verify run at 9931c1a35, distinguish host/baseline failures from collection changes, and repair reproducible regressions in an isolated worktree.

## Notes

Focused repair c77c9102314adb85633175c3e31cc56042670806 completes top-level FolderTableHandle/FolderTableSourceAdapter exports, exact public API expectations, and three serve-banner records. Validation: 54 public API/banner tests passed while recording intended goldens; 4 committed API/banner checks passed in normal comparison mode; Ruff check and format, diff whitespace check, and actual pre-commit hooks passed. Reproduced native watcher failure on current main 9d99df3ed as well as candidate; same baseline test passes with supported polling mode. Independently reproduced KPress viewport lookup failure on main with external UV_PROJECT_ENVIRONMENT and no .venv link; after linking each exact locked environment, the single scrollspy session passes on main (KPress 0.3.11) and candidate (0.3.10), with identical complete JSON. Original verify log ended without summary and had no running process; not all printed failures can be classified from that incomplete log. Parent requested no further broad local run because host load exceeded 169 and owns full stack CI verification under mb-r7zc. No push performed.
