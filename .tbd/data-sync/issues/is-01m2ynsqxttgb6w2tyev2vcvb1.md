---
type: is
id: is-01m2ynsqxttgb6w2tyev2vcvb1
title: "PR #140 Bugbot: migrate_layout must refuse future formats before taking the home lock"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-20T05:49:35.541Z
updated_at: 2026-09-20T07:15:58.456Z
started_at: 2026-09-20T06:53:08.013Z
closed_at: 2026-09-20T07:15:58.454Z
close_reason: "Fixed in da73b878: migrate_layout refuses future formats before taking the home lock."
resolution: null
duplicate_of: null
---
Cursor Bugbot on https://github.com/jlevy/metabrowser/pull/140 (Medium): `migrate_layout` documents that a future layout or config raises `FutureLayoutFormatError` before anything is written, but it takes `application_home_lock` and then reads layout/config with default `shared=\"repair\"` before `_refuse_future` runs. A direct call can create or flock `cache/locks/home.lock` first.

Fix on `claude/v011-cache-format-foundation` (#140), then rebase the stack up. Do not merge to main.

## Notes

Fixed locally in da73b878 on PR 140; 53 layout tests and format/lint passed. Restacked upward. Push, full gate, CI, and thread disposition remain pending. See mb-rldx.
