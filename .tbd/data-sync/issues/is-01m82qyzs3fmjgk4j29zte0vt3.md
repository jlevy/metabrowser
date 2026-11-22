---
type: is
id: is-01m82qyzs3fmjgk4j29zte0vt3
title: Honor explicit native Command-L consent for cache acquisition
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T23:02:51.414Z
updated_at: 2026-11-22T23:04:27.139Z
started_at: 2026-11-22T23:04:27.133Z
---
Submitting a GitHub target in the native Open URL dialog explicitly requests the cache acquisition. Carry this intentional consent through runtime discovery and duplicate handling. Preserve first-acquisition confirmation for CLI-triggered, Finder, and external URL opens that did not obtain native consent. Cover both request paths and cached fast paths.
