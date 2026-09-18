---
type: is
id: is-01m2s5c9jf071q4nbn7v8vxwxe
title: Publish a validated staging store and reuse a cache hit
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
created_at: 2026-09-18T02:26:25.487Z
updated_at: 2026-09-18T02:30:19.688Z
started_at: 2026-09-18T02:26:28.629Z
---
Write store.yml and state.yml in the staging entry, take the store lease, and rename into repository-stores/<store-key> under the store lock (or discard staging when a same-identity store is already present). Then publish sources/<slug>/ with source.yml and store-alias.yml as the sole visibility commit. An alias that already names this store succeeds; an alias that names a different store is a typed conflict and leaves the new store unreferenced. A later acquire of the same file:// source reuses the published store without fetching. No CLI wiring, no serving, no blob prefetch, no --no-serve.

## Notes

PR https://github.com/jlevy/metabrowser/pull/144 on cursor/v011-cache-publish-reuse-bd04 HEAD 2387b6d0, stacked on #143. Lands publish_from_staging and acquire_file_source: store records in staging, lease, repository-stores rename or same-identity reuse, source alias as visibility commit. Cache hit skips fetch. AliasConflictError leaves the existing alias. CLI still fails closed; no serving; no blob prefetch. Do not close until review+CI.
