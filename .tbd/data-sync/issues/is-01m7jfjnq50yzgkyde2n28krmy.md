---
type: is
id: is-01m7jfjnq50yzgkyde2n28krmy
title: "Grouped tree route: skip a queued pass whose client has disconnected (#466 review C3)"
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys3bp2ndx4v4m26exf0hz
created_at: 2026-11-16T15:28:28.388Z
updated_at: 2026-11-20T17:09:09.153Z
---
Review C on #466 (C3): with the admission lock, aborted grouped requests (a superseded choice, a pruned prefetch) still run their full pass in turn. After acquiring the lock, check await request.is_disconnected() and skip assemble_grouped_tree; first confirm uvicorn reports an aborted fetch as a disconnect.
