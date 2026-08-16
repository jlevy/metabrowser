---
type: is
id: is-01kzsb4jzq5a37evdz4bk0dqg4
title: "Repo cache: cache store (path derivation, flock, temp-and-rename publication, sidecar)"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
created_at: 2026-08-11T21:19:58.966Z
updated_at: 2026-08-16T08:05:43.426Z
extensions:
  linear:
    id: 72de9d89-2da1-484f-b3bf-1a9e3204a9bb
    linked_at: 2026-08-16T08:05:43.426Z
---
repo_cache.py: root from METABROWSER_CACHE_DIR else ~/.metabrowser/cache; repos/<host>/<owner>/<repo> via urlsplit + SCP regex; lowercase and sanitize segments with short-hash suffix when sanitizing changes the name; fcntl.flock beside the repo dir; clone to temp inside the cache root then rename so a killed clone is never served; sidecar JSON beside (not inside) the repo dir.
