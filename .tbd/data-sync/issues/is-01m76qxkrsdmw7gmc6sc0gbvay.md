---
type: is
id: is-01m76qxkrsdmw7gmc6sc0gbvay
title: Rerun the WebKit gate under normal conditions
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T02:03:22.264Z
updated_at: 2026-11-22T21:10:08.820Z
---
The gate ran with Low Power Mode on (WebKit drew at 30 fps), the screen locked, and load average 9-15 from other agents. An unlocked trial matched the source-view ratio. mb-551q landed in jlevy/metabrowser#367; after it the source view's first Load more on the gate's 16 MiB file still measured 2.25-2.46x Chrome (mb-dl7d). A clean run (make macos-webkit-gate, about 15 min, needs Chrome) with the screen unlocked and Low Power Mode off should confirm every verdict; the owner then decides whether the remaining failures call for the brief's Electron fallback (mb-gvtw).

## Notes

2026-11-22: raised to P1, since mb-1d8p requires the WebKit gate rerun on the candidate before the signed build. It needs the quiet host from mb-0msg (Low Power Mode off, disk freed).
