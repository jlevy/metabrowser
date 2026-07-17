---
type: is
id: is-01kxry26gbsyz8w0s02f18j5fv
title: "Review C6: mtime_cache holds lock across os.stat and deep-copies every hit; no dedicated test file"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:05.515Z
updated_at: 2026-07-17T21:00:05.515Z
---
mtime_cache.py:93-110: two-phase stat outside lock; deepcopy cost noted; add tests/test_mtime_cache.py covering hit/miss/absent.
