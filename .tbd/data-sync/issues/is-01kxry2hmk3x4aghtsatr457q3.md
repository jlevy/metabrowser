---
type: is
id: is-01kxry2hmk3x4aghtsatr457q3
title: "Review C9: duplicate divergent HTML escaping (app.js:108 esc via DOM vs plugin_sdk.js:129 regex)"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:16.915Z
updated_at: 2026-07-17T21:00:16.915Z
---
esc() creates a DOM element per call in tree hot loops; converge on the regex implementation.
