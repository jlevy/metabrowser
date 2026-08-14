---
type: is
id: is-01kzz4ehz2b8pr1xky5hvgr2mp
title: "Future: Add configured static-site and published-route adapters"
kind: feature
status: closed
priority: 3
version: 7
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md
labels: []
dependencies: []
parent_id: is-01kzz211w19g9y39ct7qf0hy1z
created_at: 2026-08-14T03:18:32.151Z
updated_at: 2026-08-14T05:20:51.214Z
closed_at: 2026-08-14T05:20:51.214Z
close_reason: Configured static-site route adapters are implemented, reviewed, and verified.
---
Design separate MkDocs, Docusaurus, Jekyll, and comparable adapters that translate source targets only after exact lookup and only from explicit or strong project configuration. Include published root-route ownership, source-to-output candidates, diagnostics, collision handling, and tool-specific validation without changing /view/ repository semantics.
