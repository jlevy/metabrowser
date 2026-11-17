---
type: is
id: is-01m7m4mtp2jmjtm979sy4kpzb5
title: "Brief change line: the modified (M) ink reads clearly yellow, dark only for legibility"
kind: feature
status: closed
priority: 2
version: 2
labels:
  - ui
  - design-tokens
dependencies: []
created_at: 2026-11-17T06:55:53.527Z
updated_at: 2026-11-17T07:36:30.302Z
closed_at: 2026-11-17T07:36:30.301Z
close_reason: Done in jlevy/metabrowser#506 (claude/pulls-row-indent)
resolution: null
duplicate_of: null
---
In a brief change line such as "2 A, 45 M" (the Diff summary, the Pulls rows, the pull request header), the modified status count is a very dark yellow whose saturation is too low: it reads as olive/brown rather than yellow. It should clearly be yellow, only dark enough to read against the background. Keep the 4.5:1 text contrast in both themes.
