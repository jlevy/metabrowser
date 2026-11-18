---
type: is
id: is-01m7p8a6b7gj2m97m41avs79hw
title: "Relocating the cache home re-lists every Diff summary: a manifest's key names the store's absolute path"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
created_at: 2026-11-18T02:38:28.198Z
updated_at: 2026-11-18T02:38:28.198Z
---
Review of #528 (A1 side finding). comparison_cache_key puts store_tag(git_dir) in the key, and store_tag hashes the absolute store path (http_caching.py), so the bank's manifests miss after the cache home moves. Decide whether the kept manifest's identity should name the store by key rather than path.
