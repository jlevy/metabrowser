---
type: is
id: is-01m7v62n9f3y3qh0qxe9m6ap2y
title: "Markdown: honor GitHub's allowed HTML attributes (align, width, height) so the README's centered 192px icon renders as on github.com"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T00:35:36.365Z
updated_at: 2026-11-20T00:36:08.337Z
started_at: 2026-11-20T00:36:08.335Z
---
Owner, 2026-11-19, verbatim: "the metabrowser README.md has the main image, the metabrowser icon, at the top of the readme and it's nicely small and centered on GitHub.com and github renders it nicely. But in our rendering, it's large and left-aligned. We should have the same rendering by default as GitHub's own web browser." README.md line 1: <p align="center"><img src="images/metabrowser-icon.png" alt="Metabrowser app icon" width="192"></p>, then <h1 align="center">.
