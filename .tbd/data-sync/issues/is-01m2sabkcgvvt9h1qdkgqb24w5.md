---
type: is
id: is-01m2sabkcgvvt9h1qdkgqb24w5
title: Best-effort last_opened_at on a cache hit
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-18T03:53:25.648Z
updated_at: 2026-09-18T04:01:00.695Z
started_at: 2026-09-18T03:53:28.639Z
---
Source recency is optional bookkeeping in the source state.yml. After a successful file:// acquire or cache hit, try to write last_opened_at. A read-only home, full disk, or contended alias lock must log the dropped timestamp and still return the published alias. Do not call open_cache for this write. Do not fail the hit. No serving. Pin: writable --no-serve then --api /api/cache/sources shows last_opened_at; a 0500-home hit still prints the same slug/store/revision.

## Notes

PR #151 CI green: all 7 checks on dc4223a0. Best-effort last_opened_at; dropped writes do not fail the hit. Do not close until review.
