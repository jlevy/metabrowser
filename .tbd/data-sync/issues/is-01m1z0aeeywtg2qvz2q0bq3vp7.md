---
type: is
id: is-01m1z0aeeywtg2qvz2q0bq3vp7
title: Complete canonical path conversion across host readers and plugin routes
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T22:37:46.831Z
updated_at: 2026-09-08T00:02:44.710Z
closed_at: 2026-09-08T00:02:44.709Z
close_reason: Canonical identities now cross to native paths through shared safe/plugin helpers; activity, structured, diff and walk readers updated. SDK 0.6 pins the observable change. Focused boundary tests and real-browser percent path selection pass.
resolution: null
duplicate_of: null
---
PR 101 review reproduced a valid percent filename failing through its human-facing /view URL. Additional host crossings still use canonical provider paths directly as filesystem paths: structured plugin, plugin_api.resolve_path, active tracker, folder README/container/content routes. Verify application boundaries with percent filenames and decode exactly once for filesystem access while retaining identity for provider and overlay lookups.
