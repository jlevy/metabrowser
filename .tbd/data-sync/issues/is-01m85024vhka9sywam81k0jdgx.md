---
type: is
id: is-01m85024vhka9sywam81k0jdgx
title: Treemap tooltips match the navigation's icon, size, and age formatting
kind: task
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/764
    at: 2026-11-23T20:35:17.514Z
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T20:02:52.399Z
updated_at: 2026-11-23T20:35:18.686Z
started_at: 2026-11-23T20:02:58.504Z
closed_at: 2026-11-23T20:35:18.686Z
close_reason: "Done in PR #764 (layer 8 of stack #725)"
resolution: null
duplicate_of: null
---
Requested in manual testing: the treemap tooltip (tooltipHtml in treemap-map.js) shows the path, 'N files · size', and a toLocaleString timestamp. Give it the navigation columns' file-type or folder icon, the rounded size in the .size hue, the bold file count, and the shared compact age with its freshness class (MetabrowserFormatters.age).
