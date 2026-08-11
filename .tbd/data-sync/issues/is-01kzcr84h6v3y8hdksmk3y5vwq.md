---
type: is
id: is-01kzcr84h6v3y8hdksmk3y5vwq
title: Render all chrome file paths in the sans nav face
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kzcr7qzp4j0x9h694b8evywa
created_at: 2026-08-06T23:58:59.109Z
updated_at: 2026-08-07T00:10:01.949Z
closed_at: 2026-08-07T00:10:01.949Z
close_reason: "Implemented on feat/quick-file-palette (PR #22): chrome typography rule documented in styles.css with an enforced exception list, .kbd component added and applied, T bound alongside /, palette rows restyled to the file-header weight hierarchy. make verify green."
---
Every file path shown in chrome — full paths, parent paths, and ancestor segments — uses the sans UI face and the nav type ramp, matching the Navigator tree, header path, and file-header path (which are already correct).

Known offenders found in audit of src/metabrowser/static/styles.css:
- .search-palette-description (the parent-path line under each Quick File result) — font-family: var(--font-mono)
- .tally-tree — font-family: var(--font-mono); renders directory names
- .tree-truncation-note code — mono inline code inside a chrome banner; confirm what it renders and convert if it is a path

Audit every remaining var(--font-mono) use site and classify each as chrome or content. Convert chrome; leave content.

Stays monospaced (rendered content, not chrome): code.hljs, .code-block code, .md-body code, .log-event-raw, .metabrowser-kpress-error-detail, .compression-badge glyph.

Open question to settle in the audit: .log-event-header is chrome but shows structured log values rather than paths.

Update docs/design-system.md, which currently states 'code and paths use monospaced text' — that path rule is the thing being reversed.
