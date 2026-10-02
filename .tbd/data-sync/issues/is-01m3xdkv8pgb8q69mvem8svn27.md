---
type: is
id: is-01m3xdkv8pgb8q69mvem8svn27
title: "Landing gate: restore STRUCTURED_CACHE_SIZE=0 and the diff document hook on non-patch files to 0.11.0"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3wgefqnj91f8avyyv4x8t5w
created_at: 2026-10-02T04:23:01.128Z
updated_at: 2026-10-02T04:23:01.128Z
---
Found by the landing-gate data differential (20,234 comparisons of v0.11.0 against the stack on regular folders, zero unexplained) and reproduced on the tip 8879c4de. (1) STRUCTURED_CACHE_SIZE=0: cachetools.LRUCache(maxsize=0) raises on every store where functools.lru_cache(maxsize=0) cached nothing, so /api/plugin/structured/parsed answers plugin_error. (2) /api/plugin/diff/document answers 404 for a file not named .patch or .diff; v0.11.0 parsed any file, and a third-party plugin can route other names to the diff kind. Both introduced by commit 5682448f. Fix as a new layer above #265 on branch codex/v012-gate-fixes-2, with an independent review, then re-run the three landing-gate checks on the new tip.
