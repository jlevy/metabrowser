---
type: is
id: is-01m85024vhka9sywam81k0jdgx
title: Treemap tooltips match the navigation's icon, size, and age formatting
kind: task
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T20:02:52.399Z
updated_at: 2026-11-23T20:02:58.506Z
started_at: 2026-11-23T20:02:58.504Z
---
Requested in manual testing: the treemap tooltip (tooltipHtml in treemap-map.js) shows the path, 'N files · size', and a toLocaleString timestamp. Give it the navigation columns' file-type or folder icon, the rounded size in the .size hue, the bold file count, and the shared compact age with its freshness class (MetabrowserFormatters.age).
