---
type: is
id: is-01m7nnxrj9txmcjawfmkz6frad
title: "App: accept https GitHub URLs in AppDelegate.request and File > Open Location…"
kind: feature
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7nnxsky2r2jf9d5n3ac3vty
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-17T21:17:06.505Z
updated_at: 2026-11-18T20:21:02.955Z
closed_at: 2026-11-18T20:21:02.954Z
close_reason: Landed in jlevy/metabrowser#539 (AppDelegate.requestLink accepts https GitHub links, resolves with metab --present --dry-run --format json, shows refusal.message, joins the repository's SessionRoot or starts metab HANDOFF --no-open --exit-on-eof) and jlevy/metabrowser#560 (File > Open Location shipped as File > Open URL..., Command-L, GitHub URLs only, validated by GitHubLink then the dry run)
resolution: null
duplicate_of: null
---
Phase 1, apps/macos. Today non-file URLs are dropped silently. Accept https from open -a/-b; Open Location sheet validates with metab --present --dry-run --json; show metab's reason for refused URLs. Join a matching session or start metab URL --no-open --exit-on-eof.
