---
type: is
id: is-01kzz47gp1hnjbhjv9xa1nxmze
title: "PR #35 review R5: live inventory events trigger an unbatched full-tree ARIA resync"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzz46ttyre78pjmkxynpfh3z
created_at: 2026-08-14T03:14:41.473Z
updated_at: 2026-08-14T03:32:03.050Z
closed_at: 2026-08-14T03:32:03.050Z
close_reason: "Fixed in 78ee53e: added scheduleTreeSynchronize/synchronizeTreeNow; event-driven paths coalesce into one repair per task."
---
applyCellPatch ends in treeKeyboard.synchronize() on every return path and fileStoreApplySnapshot calls it once per entry (app.js:4805-4809). synchronize() is O(rows x depth) DOM work. scheduleFilterReapply already debounces the analogous filter walk for the same reason. Add a coalescing scheduleTreeSynchronize for event-driven paths.
