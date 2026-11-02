---
type: is
id: is-01m6f3nakaknkwvc7j976xxqcg
title: "Several servers on one cache: report what is slow or confusing"
kind: task
status: open
priority: 3
version: 1
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T21:46:47.273Z
updated_at: 2026-11-02T21:46:47.273Z
---
Checked 2026-11-02: two servers took ports 8411 and 8412, answered in 2.45 s, and five at once were fine. A never-fetched PR answers in about 8 s. --port silently moves to the next free port, shown only in the printed URL. No change made; decide whether the moved port deserves a line of its own.
