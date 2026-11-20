---
type: is
id: is-01m7v62n9f3y3qh0qxe9m6ap2y
title: "Markdown: honor GitHub's allowed HTML attributes (align, width, height) so the README's centered 192px icon renders as on github.com"
kind: bug
status: closed
priority: 2
version: 7
delegate: claude-code@spud10.local
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T00:35:36.365Z
updated_at: 2026-11-20T17:00:12.558Z
started_at: 2026-11-20T00:36:08.335Z
closed_at: 2026-11-20T02:31:43.309Z
close_reason: Merged in PR 626
resolution: null
duplicate_of: null
---
Owner, 2026-11-19, verbatim: "the metabrowser README.md has the main image, the metabrowser icon, at the top of the readme and it's nicely small and centered on GitHub.com and github renders it nicely. But in our rendering, it's large and left-aligned. We should have the same rendering by default as GitHub's own web browser." README.md line 1: <p align="center"><img src="images/metabrowser-icon.png" alt="Metabrowser app icon" width="192"></p>, then <h1 align="center">.

## Notes

PR #626 (claude/markdown-github-attributes, head aff9d4275 after review A (A1-A4 fixed, dispositions posted); CI 22 pass, 1 skipped (stack-integration), 2026-11-20). Cause: the inert allowlist (inert_html.py, static/inert-html.js) dropped align except on td/th and all width/height, so every untrusted render drew the icon at 512 px against the left edge. KPress 0.3.5 (bundled in 0.12.1 installs) also dropped p/h align; the pinned KPress 5a8e9ae keeps it. KPress CSS (height:auto, cell text-align, border-box) overrode the hints; shell CSS in styles.css restores them. Allowlist source: html-pipeline SanitizationFilter DEFAULT_CONFIG, the subset KPress also keeps. KPress follow-ups not fixed: its sanitizer drops valign/hspace/vspace/clear/nowrap/dir/li value/details open; GFM pipe-table column alignment lost; tables min-width:100% so table align/width have no effect; 1rem margin-block raises inline badges. Overlaps mb-4cwy (its allowlist half).
