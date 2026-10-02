---
type: is
id: is-01m3xdkv8pgb8q69mvem8svn27
title: "Landing gate: restore STRUCTURED_CACHE_SIZE=0 and the diff document hook on non-patch files to 0.11.0"
kind: bug
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3wgefqnj91f8avyyv4x8t5w
created_at: 2026-10-02T04:23:01.128Z
updated_at: 2026-10-02T20:47:23.893Z
---
Found by the landing-gate data differential (20,234 comparisons of v0.11.0 against the stack on regular folders, zero unexplained) and reproduced on the tip 8879c4de. (1) STRUCTURED_CACHE_SIZE=0: cachetools.LRUCache(maxsize=0) raises on every store where functools.lru_cache(maxsize=0) cached nothing, so /api/plugin/structured/parsed answers plugin_error. (2) /api/plugin/diff/document answers 404 for a file not named .patch or .diff; v0.11.0 parsed any file, and a third-party plugin can route other names to the diff kind. Both introduced by commit 5682448f. Fix as a new layer above #265 on branch codex/v012-gate-fixes-2, with an independent review, then re-run the three landing-gate checks on the new tip.

## Notes

2026-10-02: PR #267 (codex/v012-gate-fixes-2, base codex/v012-release-check), head 14fcdb85, CI 9/9 green, in native stack #218 below #260. Six commits: structured cache size 0 or less caches nothing; the diff document hook parses any file name (plus CHANGELOG entries for the typed 404 on an unreadable file and for compressed patches); --show reads the dotenv chain as often as 0.11.0; no stray quote attribute on tree folder rows; 21 px line pitch for unhighlighted source (new paint-exempt parity row source.line-pitch); negative byte bounds answer a typed empty result. Not matched to 0.11.0 on purpose: at -2 0.11.0 read unbounded, at -3 and below it answered plugin_error; a CHANGELOG entry for that is owed on #260's branch. INDEPENDENT REVIEW NOT FINISHED: no report was recorded before the session ended; run it again before closing this bead.

2026-10-01: scope widened after the browser differential (1,320 steps, tip f62c16b1). Added to the same layer: (3) a stray attribute on every tree folder row, '<div "="" ...>', from app.js ending the row template with dataTipNumberAttr(...) plus an extra quote (commit 26c9eb00; present on 481b64b7 line 1775); (4) line pitch of a non-highlighted source window is 18 px where 0.11.0 drew 21 px, from 'pre.code-block.metabrowser-source-lines { display: grid }' (40,000 lines: 720,073 px against 840,073 px). Items 1-2 (STRUCTURED_CACHE_SIZE=0; diff document hook on non-patch names) reproduced on 8879c4de by the coordinator and by the docs agent. Branch codex/v012-gate-fixes-2 from 481b64b7; the PR is appended to native stack #218 below #260.
