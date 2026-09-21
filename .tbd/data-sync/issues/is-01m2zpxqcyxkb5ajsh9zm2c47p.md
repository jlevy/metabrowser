---
type: is
id: is-01m2zpxqcyxkb5ajsh9zm2c47p
title: "DOCS-1: reconcile stale architecture-doc status lines and unbuilt seams with the built stack"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr216
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:29.071Z
updated_at: 2026-09-21T00:08:19.611Z
closed_at: 2026-09-21T00:08:19.608Z
close_reason: "Pushed 2026-09-20 in the restack of stack #218 onto main (through #209 and #220). Single pre-push gate on macOS: 3061 passed, 2 skipped, 145 golden transcripts. Awaiting CI."
resolution: null
duplicate_of: null
---
Finding DOCS-1 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under DOCS-1.

## Notes

Done on stab/docs (f6326422, 3bda1068, eb7abf1d; pending integration into PR 216): status lines and seam tables corrected in three architecture documents, every path verified against the tree. Follow-ups left open: (1) arch-views-models-routes.md:206 still names resolve_content/stat_content/read_content_window as shipped; reserved for the content-reader build mb-0um4. (2) arch-external-resources-and-views.md 'Planned Implementation Seams' names two more nonexistent items (plugin_loader/provider_addresses.py encode_provider_address_atom; ResourceKindSpec) and lists several rows that are in fact built (capability_types.py, capability_discovery.py, artifact_contracts.py, static/resource-context.js, static/view-composition.js); marking each row needs a judgment call on 'Virtual navigation'. (3) arch-git-and-comparison-sources.md opens with about 40 lines of route narrative inside its Status block.
