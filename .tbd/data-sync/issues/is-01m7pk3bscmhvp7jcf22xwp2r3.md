---
type: is
id: is-01m7pk3bscmhvp7jcf22xwp2r3
title: "Pin errno.EISDIR in the directory-lock fallback test (review B1 of #551)"
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
created_at: 2026-11-18T05:46:58.731Z
updated_at: 2026-11-20T17:28:23.457Z
---
tests/test_cache_atomic.py:369-373 parametrizes over the set it tests, so dropping errno.EISDIR from _DIRECTORY_LOCK_UNSUPPORTED_ERRNOS passes. Name it explicitly or assert membership.
