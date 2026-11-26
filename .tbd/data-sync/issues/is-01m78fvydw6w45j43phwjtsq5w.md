---
type: is
id: is-01m78fvydw6w45j43phwjtsq5w
title: Plugin runtime package metabrowser_sdk, shared by the server, workers, and authors
kind: task
status: open
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvywxsmc0m4481ypk3zbq
  - type: blocks
    target: is-01m8bfwztw84vfapjmyap7ta72
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:07.899Z
updated_at: 2026-11-26T08:37:20.277Z
started_at: 2026-11-26T08:35:34.370Z
---
Phase 1 (plan: The Plugin Runtime, Key Decision 1). A standard-library-only package, metabrowser_sdk, published as its own distribution that Metabrowser depends on at one exact version; the host puts its copy first on a worker's path. It holds one implementation of every name metabrowser.plugin_api.__all__ exports on main (94, of which 55 are the table-source API) and CLIError: the inventory identity codec moved out of inventory_engine.contract, the path helpers and root callbacks, ArtifactPath with gz_io and content_errors, the content reader and its types, LogEvent, LogParser, the adapter registry, the table-source protocol with its helpers and bounds, the host services (agent-chart projection and memo, jsonl_parse_max_bytes, plugin_cache_directory), HookRequest and HookResponse, and the worker loop. metabrowser.plugin_api re-exports it, so main's documented imports keep working in process. Host-facing functions are bound two ways: to the server's own in process, and to host calls in a worker. An import-boundary test holds it to the standard library. Release mechanics for a second distribution: versioning, publish order, and its first-party entry. The worker client, the header policy, and the conformance test were split out: mb-nes2, mb-x1j5, mb-sbjf. If the owner chooses Key Decision 1 option C instead, the package is injected as metabrowser and is not published under that name.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
