---
type: is
id: is-01m76qxkrsdmw7gmc6sc0gbvay
title: Rerun the WebKit gate under normal conditions
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T02:03:22.264Z
updated_at: 2026-11-12T02:03:22.264Z
---
The gate ran with Low Power Mode on (WebKit drew at 30 fps), the screen locked, and load average 9-15 from other agents. An unlocked trial matched the source-view ratio, but a clean run (make macos-webkit-gate, about 15 min, needs Chrome) with the screen unlocked and Low Power Mode off should confirm every verdict, after mb-551q lands.
