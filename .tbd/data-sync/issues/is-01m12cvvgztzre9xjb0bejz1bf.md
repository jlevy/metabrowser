---
type: is
id: is-01m12cvvgztzre9xjb0bejz1bf
title: "PR #86 review R7: MAX_WALKS=2 makes a third tab evict an active session"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:59:01.662Z
updated_at: 2026-08-27T19:59:01.662Z
---
src/metabrowser/settings.py:292. GIT_HISTORY_SESSION_MAX_WALKS=2 vs MAX_ENTRIES=8; three tabs thrash with full replays on each 410. Raise bound or degrade better. PR #86 comment 3873347212
