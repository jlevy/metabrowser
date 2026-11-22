---
type: is
id: is-01m82ckpd2h34zw1tqdv7cqedx
title: Show the accepted GitHub URL forms in Open URL help
kind: task
status: in_progress
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/694
    at: 2026-11-22T19:57:11.610Z
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-22T19:44:26.981Z
updated_at: 2026-11-22T19:57:16.953Z
---
Keep Command-L help compact. List the three equivalent examples https://github.com/jlevy/metabrowser, github.com/jlevy/metabrowser, and jlevy/metabrowser. The shortcut parser is a separately tracked parallel change.

## Notes

Implemented on b0e193f2e. The AppKit probe checked all three exact examples and their placement in light and dark appearances, the accessibility label and initial focus, and the Return and Escape actions. Exact hosted general and macOS gates pending.
