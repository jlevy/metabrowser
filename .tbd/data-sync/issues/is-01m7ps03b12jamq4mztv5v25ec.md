---
type: is
id: is-01m7ps03b12jamq4mztv5v25ec
title: One ROOT/--path reading shared by serve mode and --present (#540 A10)
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7nyeb57h28trbdp2m1hy2wk
created_at: 2026-11-18T07:30:03.233Z
updated_at: 2026-11-18T07:30:03.233Z
---
Deferred from PR #540 review A10: _resolve_local duplicates run_serve's ROOT and --path reading with no test binding them. Folds into mb-2wfk (the shared local-open resolver); a test through run_serve needs a subprocess (SIGINT handler, env writes).
