---
type: is
id: is-01m7ps03b12jamq4mztv5v25ec
title: One ROOT/--path reading shared by serve mode and --present (#540 A10)
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-18T07:30:03.233Z
updated_at: 2026-11-20T17:22:26.617Z
---
Deferred from PR #540 review A10: _resolve_local duplicates run_serve's ROOT and --path reading with no test binding them. Folds into mb-2wfk (the shared local-open resolver); a test through run_serve needs a subprocess (SIGINT handler, env writes).
