---
type: is
id: is-01m2zpwvxd9vp6vpn587bsz6p7
title: "S216-9: decide and reconcile the plugin content-reader API with the spec, plugins doc, and architecture map"
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr216
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:00.933Z
updated_at: 2026-09-21T02:56:58.484Z
closed_at: 2026-09-21T02:56:58.481Z
close_reason: "Built and pushed to PR 216 as 5682448f (head 255b2b9c). Four calls through plugin_api over an opaque ContentRef with no path: resolve_content, resolve_content_container, stat_content, read_content_window. Every read takes an explicit byte maximum with no unbounded variant; filesystem reads in the thread pool, pinned reads through the pooled cat-file actors; one catchable error family whose http_status is pinned against what the routes already answer. All four built-in data hooks now hold no Git import and no source-kind branch (verified by grep). content_source() removed: introduced in the unreleased 0.11.0, so no released consumer, and it was the unrestricted object the architecture document forbids; no PLUGIN_SDK_VERSION bump, since the gate covers the browser SDK contract. Spec item, plugins doc, both architecture documents and the CHANGELOG now agree with the code. Gate: 3093 passed, 2 skipped, 145 goldens."
resolution: null
duplicate_of: null
---
Finding S216-9 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-9.

## Notes

Decision 2026-09-20 (user): BUILD the bounded, source-agnostic content reader through plugin_api and move the built-in binary/structured/agent-log/diff sidekicks onto it; then make the spec box, docs/plugins.md, the architecture doc, and the parity map agree. Starts after the S216 core and CLI fix branches are integrated, because it edits the same sidekick files.
