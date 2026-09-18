---
type: is
id: is-01m2s9k0ratabccfcr0ncj0ac6
title: Reuse a cache hit against a home the process cannot write
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-18T03:40:00.138Z
updated_at: 2026-09-18T03:46:00.272Z
started_at: 2026-09-18T03:40:03.454Z
---
A published file:// cache hit must inspect without writing: no open_cache, no lock files, no Git floor, no fetch. acquire_file_source currently always open_cache when the home exists, so a 0500 home fails even when the alias is already published.

On an existing current-format home, find the published source first with shared=keep record reads. A hit returns that alias. A miss still open_cache (sweep, reclaim) then fetches. A future layout is refused before any write. A miss against a home without owner write fails instead of fetching. No last_opened_at in this slice. No serving. No CI Git pin.

Pin: second --no-serve after dropping owner-write on the home prints the same slug/store/revision; open_cache is not called on a hit.

## Notes

Hit-first acquire_file_source: keep-read layout/config then _find_published, return without open_cache. Miss still open_cache then fetch. Future layout refused before write. 0500 miss fails PrivateStorageError. Golden cli-cache-readonly-hit.txt. Branch cursor/v011-cache-readonly-hit-bd04 stacked on orphan-reclaim. Do not close until review.
