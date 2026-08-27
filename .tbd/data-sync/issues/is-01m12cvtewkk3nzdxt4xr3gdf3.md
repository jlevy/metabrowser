---
type: is
id: is-01m12cvtewkk3nzdxt4xr3gdf3
title: "PR #86 review R4: session recovery replays whole prefix unbounded, re-entrancy hazard"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:59:00.572Z
updated_at: 2026-08-27T19:59:00.572Z
---
src/metabrowser/static/git-panel.js:1761. After idle-TTL reap, recovery replays every page up to restoreOrdinal (400 requests at ordinal 100k); recoverHistorySession can recurse without depth guard. Bound replay or restore to nearest cached page. PR #86 comment 3873346712
