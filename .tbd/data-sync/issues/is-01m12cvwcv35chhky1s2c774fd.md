---
type: is
id: is-01m12cvwcv35chhky1s2c774fd
title: "PR #86 review R9: history window read() validates viewportHeight but not scrollTop"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:59:02.554Z
updated_at: 2026-08-27T19:59:02.554Z
---
src/metabrowser/static/git-history-window.js:244. NaN scrollTop poisons segmentStart permanently; add Number.isFinite guard like viewportHeight. PR #86 comment 3873347683
