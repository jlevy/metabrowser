---
type: is
id: is-01m78fw2nz4rpf95kybngf40zq
title: Reload plugin sources without restarting the server
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:12.254Z
updated_at: 2026-11-12T18:21:12.254Z
---
Phase 4 (plan: Lifecycle). The registry as a generation object swapped whole; data hooks through one dispatch route /api/plugin/{plugin}/{route}; /plugin-static/, the classifier, and derived caches keyed by generation; debounced watches on plugins.yml and environment fingerprints; workers drained and restarted when their environment changes; a plugins-changed event and a page reload offer; --plugins-reload through the host-mode control socket once it exists.
