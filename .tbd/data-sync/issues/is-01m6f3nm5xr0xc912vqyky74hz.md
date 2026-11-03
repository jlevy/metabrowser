---
type: is
id: is-01m6f3nm5xr0xc912vqyky74hz
title: Re-run the folder comparison after this branch merges
kind: task
status: open
priority: 1
version: 2
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T21:46:57.084Z
updated_at: 2026-11-03T02:31:12.260Z
---
This branch changes plain-folder narrow diffs, and possibly toggles. Extends mb-2g6f's re-run on the head to be tagged; the sign-off record must then name this branch's changes too.

## Notes

Review A of PR #284 (A6): include a commit of more than 50 files in the plain-folder re-run. On a folder nothing is kept, so each deferred file costs the manifest run again (about 0.7 s at 1,183 files), one after the other; the scheduler's one-at-a-time hydration is a folder-visible change beside the narrow diffs and toggles.
