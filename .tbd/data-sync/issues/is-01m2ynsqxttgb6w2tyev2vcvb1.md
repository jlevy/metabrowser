---
type: is
id: is-01m2ynsqxttgb6w2tyev2vcvb1
title: "PR #140 Bugbot: migrate_layout must refuse future formats before taking the home lock"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-20T05:49:35.541Z
updated_at: 2026-09-20T05:49:35.541Z
---
Cursor Bugbot on https://github.com/jlevy/metabrowser/pull/140 (Medium): `migrate_layout` documents that a future layout or config raises `FutureLayoutFormatError` before anything is written, but it takes `application_home_lock` and then reads layout/config with default `shared=\"repair\"` before `_refuse_future` runs. A direct call can create or flock `cache/locks/home.lock` first.

Fix on `claude/v011-cache-format-foundation` (#140), then rebase the stack up. Do not merge to main.
