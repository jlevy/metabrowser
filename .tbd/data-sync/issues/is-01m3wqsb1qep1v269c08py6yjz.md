---
type: is
id: is-01m3wqsb1qep1v269c08py6yjz
title: "Landing-gate fixes: restore two regular-folder behaviors, pin two lost assertions, CHANGELOG gaps, bytecode-controlled startup pairs"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T22:01:32.470Z
updated_at: 2026-10-02T00:55:46.607Z
started_at: 2026-10-01T22:01:33.487Z
closed_at: 2026-10-02T00:55:46.605Z
close_reason: "PR #264: three regular-folder behaviors restored to v0.11.0 (hover prefetch of compound .jsonl names; size in /api/plugin/structured/parsed; non-UTF-8, CR and corrupt-compressed structured files), each with a test that fails without it; the route is identical to v0.11.0 on 125 of 126 compared paths (the one difference is a fix: an unreadable file no longer answers with an absolute host path). Two lost assertions re-pinned; CHANGELOG gaps and three errors corrected; frame_missing_px probe fixed (harness version 23); startup_pairs.py refuses mixed bytecode states and appended runs. Independent review; 47 of 47 mutations killed. CI green on the head merged above #263."
resolution: null
duplicate_of: null
---
From the landing gate's evidence audit (mb-2g6f; report in the session scratchpad at landing-gate/audit/REPORT.md, tip f62c16b1) and the startup measurement of 2026-10-01. (U1) Hover prefetch: shouldPrefetchFile in static/app.js now reads the tree row's data-ext before the path's last suffix; a served folder's rows carry the compound-tail extension, so a JSONL file with a compound name (run.codex.jsonl, data-ext='.codex.jsonl') is prefetched on hover up to the 512 KiB cap where v0.11.0 skipped every .jsonl (commit 9cb937a0 gives only a Git reason). Restore v0.11.0's behavior for a served folder: any name ending .jsonl is not prefetched; keep whatever the Git case needs. (U2) /api/plugin/structured/parsed 'size': v0.11.0 answered the file's on-disk size; the stack answers the decoded bytes read, capped at the parse limit (small.json.gz 40 -> 22; over-cap big.json 2009 -> 1000; commit 5682448f, no CHANGELOG line). Restore the on-disk size for a filesystem file, or if the content-reader design cannot know it, add a separate field and document the change; prefer restoring. Lost assertions to re-pin with tests that fail without the behavior: the Load more footer follows the content in the Markdown Source view (renderSourceView writes notice, code, footer in that order); /api/plugin/structured/parsed answers truncated: true past the cap through the route, for .json and .json.gz. CHANGELOG gaps: the built-in github plugin appears on every folder in --plugins, the serve banner's Plugins line and --doctor's count (5937a60d); ensureKindAssets appends a modulepreload link; renderSourceView emits LF for CR or CRLF sources; --plugin markdown lists place-rendered.js; --doctor is about 250 ms slower because it validates cache record contracts. Startup measurement: explorations/performance-loop/startup_pairs.py must control the bytecode regime (this session's shell sets PYTHONDONTWRITEBYTECODE=1, so agent-built environments had no .pyc and exp-037 measured both builds uncached; a cached control against an uncached candidate showed a false 3x): the harness refuses or fixes an asymmetric state and records the regime; exp-037 gets a dated addendum stating its regime and the cached-bytecode results recorded on mb-67s1.
