---
type: is
id: is-01m78fw2nz4rpf95kybngf40zq
title: Reload plugin sources without restarting the server
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:12.254Z
updated_at: 2026-11-12T21:17:48.783Z
---
Phase 5 (plan: Lifecycle). The registry as a generation swapped whole; data hooks through one dispatch route /api/plugin/{plugin}/{route} that refuses methods a hook does not declare (same-origin proof applies to every /api request; the JSON content-type rule only to POST, PUT, PATCH, and DELETE); /plugin-static/, the classifier, and derived caches keyed by generation; debounced watches on plugins.yml, environment fingerprints, and manifests; workers drained; plugins-changed event and a page reload offer; metab-plugins --reload through the host-mode control socket once it exists; a root moving to another clone swaps repository-scoped sources in place.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
