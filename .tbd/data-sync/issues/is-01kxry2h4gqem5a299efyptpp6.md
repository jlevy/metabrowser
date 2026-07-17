---
type: is
id: is-01kxry2h4gqem5a299efyptpp6
title: "Review C7: app.js selectFile lacks AbortController; fileETags/fileNeedsRevalidate unbounded"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:16.399Z
updated_at: 2026-07-17T21:00:16.399Z
---
app.js:2408 superseded fetches run to completion; ETag/revalidate maps grow without bound in long sessions (fileCache LRU only bounds the 30-entry cache).
