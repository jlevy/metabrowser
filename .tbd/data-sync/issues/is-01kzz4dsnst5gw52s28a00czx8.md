---
type: is
id: is-01kzz4dsnst5gw52s28a00czx8
title: "Route B: Add safe direct-view server and CLI routes"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4dt2aa6059jzk41yszq49
parent_id: is-01kzz03fmd769zawq6gf5d1hd7
created_at: 2026-08-14T03:18:07.273Z
updated_at: 2026-08-14T03:38:25.671Z
closed_at: 2026-08-14T03:38:25.669Z
close_reason: Implemented safe direct /view/ shell routes and segment-encoded CLI startup URLs in 58aab8d; make verify passes.
---
Register safe direct GET handling for /view/{path:path} with the existing shell and served-root path policy, including root and folder forms, malformed encoding, reserved namespaces, and refresh behavior. Change CLI startup URLs to use the shared segment-encoded /view/ contract. Add focused Starlette tests and CLI goldens. Reuse existing safe-path helpers and add no path-resolution endpoint.
