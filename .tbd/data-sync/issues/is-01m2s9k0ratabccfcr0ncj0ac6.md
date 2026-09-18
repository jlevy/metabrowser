---
type: is
id: is-01m2s9k0ratabccfcr0ncj0ac6
title: Reuse a cache hit against a home the process cannot write
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-18T03:40:00.138Z
updated_at: 2026-09-18T03:50:09.848Z
started_at: 2026-09-18T03:40:03.454Z
---
A published file:// cache hit must inspect without writing: no open_cache, no lock files, no Git floor, no fetch. acquire_file_source currently always open_cache when the home exists, so a 0500 home fails even when the alias is already published.

On an existing current-format home, find the published source first with shared=keep record reads. A hit returns that alias. A miss still open_cache (sweep, reclaim) then fetches. A future layout is refused before any write. A miss against a home without owner write fails instead of fetching. No last_opened_at in this slice. No serving. No CI Git pin.

Pin: second --no-serve after dropping owner-write on the home prints the same slug/store/revision; open_cache is not called on a hit.

## Notes

PR #150 (draft) stacked on #149 / cursor/v011-cache-orphan-reclaim-bd04. HEAD 9ec9a8d0. Local pytest 2774 passed; overlay --api goldens fail in this environment as before. Waiting on GitHub CI. Do not close until review.
