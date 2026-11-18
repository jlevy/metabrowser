---
type: is
id: is-01m7n6v8n050erzeb13c5tasar
title: Pull request diff summaries load slowly in the Pulls rows and on the PR page
kind: epic
status: in_progress
priority: 1
version: 9
delegate: claude-code@spud10.local
labels: []
dependencies: []
child_order_hints:
  - is-01m7n6v99j0bz3n0ja7mszthq9
  - is-01m7n6v9tbv4yn1xeap5zz6ryq
  - is-01m7n6vab638rqhjfdb7bb3e4n
  - is-01m7n8aqx25qnxzb6047h1ew59
  - is-01m7n8ardt2zyqya7j20f7w9ja
  - is-01m7n8arwwxqq83hsf7mm7m403
  - is-01m7nfgjv2d783zg23ykdd7kgg
hold: null
hold_until: null
created_at: 2026-11-17T16:53:36.020Z
updated_at: 2026-11-17T19:25:03.201Z
started_at: 2026-11-17T16:53:42.941Z
---
The owner reported that diff summaries (per-file line totals, the change summary) load slowly in the Pulls nav rows and on the main pull request page. Three children: prefetch and persist summaries as cache files and answer from the last persisted version first; measure the route and git/gh timings and fix the dominant cost; show the existing gentle loading box promptly whenever a summary has not loaded. Design rule: Metabrowser feels effortlessly fast, prefetch by default, never flash a spinner under ~50 ms, never leave an empty gap.
