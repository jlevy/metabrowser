---
type: is
id: is-01m2ynskxv64d74tpy85555mef
title: "PR #140 Bugbot: refuse future/missing layout before any home write"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-20T05:49:31.442Z
updated_at: 2026-09-20T06:53:07.699Z
started_at: 2026-09-20T06:53:07.679Z
---
Cursor Bugbot on https://github.com/jlevy/metabrowser/pull/140 (Medium): `open_cache` pre-reads layout so a future format is refused, but a home that already has sources/stores/quarantine/provider data and no `layout.yml` still runs `ensure_home` and the probe first. That writes `CACHEDIR.TAG` and creates the f01 skeleton before `migrate_layout` can refuse.

Fix on `claude/v011-cache-format-foundation` (#140), then rebase the stack up. Do not merge to main.
