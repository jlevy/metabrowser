---
type: is
id: is-01m78fw2nz4rpf95kybngf40zq
title: Reload plugin sources without restarting the server
kind: task
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:12.254Z
updated_at: 2026-11-26T08:37:20.290Z
started_at: 2026-11-26T08:35:34.391Z
---
Phase 5 (plan: Lifecycle). The registry as a generation swapped whole; /plugin-static/, the classifier, and derived caches keyed by generation; data hooks keep one registered route each, so the parity registry's per-route rows stay; debounced watches on plugins.yml, environment fingerprints, and manifests; workers drained; plugins-changed event and a page reload offer, with its functional parity row; metab --plugins-reload through the host-mode control socket once it exists; a subject moving to another clone swaps repository-scoped sources in place.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
