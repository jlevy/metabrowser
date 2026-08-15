---
type: is
id: is-01kzz4dtn4pw3my7gf9wsr9ebh
title: "Links A: Implement the typed standard Markdown target resolver"
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/done/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4dty54dvgw9q1aqf3s811
parent_id: is-01kzz03fwfcvam3ft3zvfwqx7g
created_at: 2026-08-14T03:18:08.291Z
updated_at: 2026-08-14T04:56:20.859Z
closed_at: 2026-08-14T04:06:30.107Z
close_reason: Implemented exact typed standard Markdown/HTML resolution with fixture/schema coverage; make verify passes.
---
Create a fully strict pure Markdown-plugin resolver for LinkIntent and ResolvedTarget. Classify allowed external URLs, protocol-relative URLs, current-document fragments, exact source-relative, parent, and served-root paths, folders, queries, and embedded resources. Decode once, preserve case, reject escapes, encoded separators, NULs, backslash traversal, and disallowed schemes, and never append extensions, select index files, or fuzzy search standard Markdown. Add a machine-readable fixture schema and pure tests.
