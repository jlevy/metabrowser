---
type: is
id: is-01m7r96aynkd71s9ehjw8y4ze7
title: "Rendered-diff names lag their scope: markdown_projection_worker, FIRST_SCREEN_MARKDOWN, prefetchMarkdown"
kind: chore
status: open
priority: 4
version: 1
labels: []
dependencies: []
parent_id: is-01m7pfyxz015mfas5phhvtqz33
created_at: 2026-11-18T21:32:19.264Z
updated_at: 2026-11-18T21:32:19.264Z
---
Found by review A15 of PR #557. markdown_projection_worker.py, createMarkdownViews, FIRST_SCREEN_MARKDOWN, prefetchMarkdown, view.markdown and diff-file-bar-markdown now serve Markdown, YAML and JSON. Rename them to say rendered, in one commit with every caller; the names are internal.
