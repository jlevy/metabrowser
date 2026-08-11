---
type: is
id: is-01kzqna4tt9t4r9z92xkzmbhrw
title: "Nav column vertical rhythm: symmetric collapsed filter bar, first row clears the tally rule"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-11T05:39:17.977Z
updated_at: 2026-08-11T05:41:57.491Z
closed_at: 2026-08-11T05:41:57.490Z
close_reason: Row-gap gated on drawer open and transitioned with the track; first tree row clears the tally rule by 6px. Browser-measured 6/6, 6/6, 6. Fixed in 36c59c7.
---
The collapsed nav filter bar sat 6px above its controls and 13px below them, and the first tree row landed flush against the tally's bottom border.
