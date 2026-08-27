---
type: is
id: is-01m12cvtt889hdcf8jpafj7jbv
title: "PR #86 review R5: reaching a distant page costs one HTTP request per page"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:59:00.935Z
updated_at: 2026-08-27T19:59:00.935Z
---
src/metabrowser/static/git-panel.js:588. replayStep only steps +/-1 from cached page; scrollbar drag to page 2000 issues 2000 sequential requests, intermediate pages evicted unrendered. Cap replay distance or add a real seek. PR #86 comment 3873346860
