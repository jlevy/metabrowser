---
type: is
id: is-01m83sewt55ghr79x3ss01cbg0
title: "CI: measure keeping wheels in the setup-uv cache (prune-cache: false)"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-23T08:48:15.684Z
updated_at: 2026-11-23T08:48:15.684Z
---
Follow-up to mb-lo7l (PR #750). setup-uv restores a pruned cache, so every CI job downloads ~100 MB of wheels from PyPI (nodejs-wheel-binaries 57.9 MiB, basedpyright, ruff, ...); run 45134271894 spent 2 m 45 s there instead of ~2 s. Measure prune-cache: false across the jobs: cache size, restore time, and uv sync time, against today's. Adopt it if restore is reliably faster than download; record the numbers beside the setting.
