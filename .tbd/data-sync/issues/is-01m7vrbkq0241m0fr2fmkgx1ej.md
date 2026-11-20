---
type: is
id: is-01m7vrbkq0241m0fr2fmkgx1ej
title: Repository store paths use a 64-hex sha256 directory name; make them short and readable
kind: task
status: closed
priority: 2
version: 5
delegate: claude-code@spud10.local
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T05:55:04.031Z
updated_at: 2026-11-20T17:00:13.077Z
started_at: 2026-11-20T05:55:54.198Z
closed_at: 2026-11-20T08:41:32.356Z
close_reason: "Merged in PR 647: store keys <readable>--<16 hex>, collision-checked; f01->f02 rename-in-place migration."
resolution: null
duplicate_of: null
---
Owner, 2026-11-20: '~/.cache/metabrowser/repository-stores/589d51b16fd8f1a20aaa68a5893f815052de0db43f00b84b9f79b8c97d18b306/repository.git ... is ridiculously long, why do we need a hash that long? We should reliably figure out the right number of bits for these IDs to avoid collisions, but keep them readable.' Choose an ID with a readable part (host/owner/repo slug) plus a short hash sized by a stated birthday-bound calculation, with collision detection rather than assumption.

## Notes

PR #647 (claude/short-store-ids). Store key = readable part of the source slug + first 16 hex digits of the store identity digest (STORE_KEY_SUFFIX_HEX_DIGITS = 16, 24, 32, 64; birthday-bound sizing beside the constant, recomputed in tests/test_cache_store_keys.py). Collisions are detected, not assumed: claim under the store lock reads store.yml ids and takes the next width; lookup finds the store at whichever candidate records its id. Layout f02; f01 stores are renamed in place by cache/store_rename.py (same inode, no re-clone; orphans become unattached--<16 hex>). Header note shows the store directory without /repository.git; tooltip and /api/source/status keep the whole path. macOS app unchanged (reads only /api/cache/sources). Left: locks/sources/<64 hex>.acquire.lock (internal reservation, named only in a wait-timeout message). Not verified locally: tests/test_cache_resolve.py case-collision test fails on origin/main too with Git 2.56.1 (fetch fails before the RefCaseCollisionError).
