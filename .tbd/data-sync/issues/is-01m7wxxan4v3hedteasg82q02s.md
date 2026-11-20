---
type: is
id: is-01m7wxxan4v3hedteasg82q02s
title: "Store keys: a clean single-dash slug plus a short deterministic base36 digest (e.g. github-com-jlevy-metabrowser-<base36>), instead of github-com--jlevy--metabrowser--<16 hex>"
kind: task
status: closed
priority: 1
version: 7
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/666
    at: 2026-11-20T22:45:01.709Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7x1jaewjm2pnxm8dnmnqdtq
hold: null
hold_until: null
created_at: 2026-11-20T16:51:21.891Z
updated_at: 2026-11-20T22:45:02.044Z
started_at: 2026-11-20T16:52:06.238Z
closed_at: 2026-11-20T22:45:02.043Z
close_reason: "Landed in PR #666 (2d8c809d4). CI passed on eebe70caf with the senior review fixes, v2 schema, and goldens. Review dispositions are recorded on the PR."
resolution: null
duplicate_of: null
---
Owner, 2026-11-20, follow-up to mb-j2cp (#647): keys like github-com--jlevy--metabrowser--589d51b16fd8f1a2 are still too long. Keep it deterministic (a digest of the source identity, never random), just encoded compactly: base36 (as strif's short id helpers do) at the number of bits #647's collision analysis needs, with the readable part a plain slug joined by single dashes. Keep the collision-escalation path (longer suffix on a claimed key) and the store rename so existing stores move without refetching.

## Notes

PR #666 (claude/base36-store-keys). One grammar for store keys and source slugs: <readable words joined by single dashes>-<first 11 base-36 chars of the identity digest read as a fraction of 1> (NAME_SUFFIX_CHARS 11/19/25/50; 56.9 bits, under 1e-9 at the 10,000 entries the routes list). Layout f03: stores move from repository-stores/ to repos/ (per-store no-replace rename, leftovers under old names, old parent removed when empty); source.yml slug rewritten and validated against the source identity; migrations from f01 and f02 via plan_store_renames/apply_renames in cache/store_rename.py. repository.git kept, one helper store_git_directory in cache/paths.py; locks/stores/ kept. macOS app reads only /api/cache/sources (slugs as opaque [a-z0-9-] cursors), no change. Not done here, left to the follow-up bead: recents, deletion contract, Time Machine, sizes.
