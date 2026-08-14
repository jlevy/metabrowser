---
type: is
id: is-01kzz4dwwjgch14nr5rhh2j1vm
title: "Obsidian D: Render attachment links and safe media wiki-embeds"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/done/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4dx62z79hwmqmec5z0kbb
parent_id: is-01kzz03gmzn17gpzrtbs6jfh1x
created_at: 2026-08-14T03:18:10.577Z
updated_at: 2026-08-14T04:56:23.998Z
closed_at: 2026-08-14T04:53:26.522Z
close_reason: Stable heading/block targets and safe attachment/media behavior pass focused and end-to-end tests.
---
Resolve attachment wiki-links and image, audio, video, and other supported media wiki-embeds through the shared safe-resource boundary. Parse bounded width and height occurrence metadata without mixing it into target lookup, preserve accessible labels and fallbacks, and represent whole-note or section transclusion as an explicit unsupported future action with a safe navigation link. Add media, hostile-target, and renderer-disposal tests.
