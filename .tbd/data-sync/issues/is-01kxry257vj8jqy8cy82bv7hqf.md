---
type: is
id: is-01kxry257vj8jqy8cy82bv7hqf
title: "Review C1: sse.py:153 sync stat() on event loop every 500ms per tailed file"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:04.219Z
updated_at: 2026-07-17T21:00:04.219Z
---
Wrap the poll-cycle stat in asyncio.to_thread; the read at sse.py:175 is already threaded.
