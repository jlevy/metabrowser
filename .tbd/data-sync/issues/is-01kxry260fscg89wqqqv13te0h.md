---
type: is
id: is-01kxry260fscg89wqqqv13te0h
title: "Review C4: watch_backends.py:264 second sync stat (is_dir) on event loop per watcher event"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:05.007Z
updated_at: 2026-07-17T21:00:05.007Z
---
Reuse the threaded lstat result (S_ISDIR of st_mode) instead of a second synchronous Path.is_dir() stat.
