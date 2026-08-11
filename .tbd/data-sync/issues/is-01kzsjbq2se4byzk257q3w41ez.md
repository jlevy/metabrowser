---
type: is
id: is-01kzsjbq2se4byzk257q3w41ez
title: "PR #30 review R4: align live and initial empty-folder semantics"
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies: []
parent_id: is-01kzshazdfnw7wz3h768kgbfmg
created_at: 2026-08-11T23:26:12.569Z
updated_at: 2026-08-11T23:29:56.166Z
closed_at: 2026-08-11T23:29:56.165Z
close_reason: Fixed with focused and full regression coverage; make verify passes (891 pytest tests and 28 golden CLI scenarios).
---
PR #30 Cursor review thread PRRT_kwDOTX174c6YaCHi. Live row patches use direct child presence while initial tree rendering defines empty by absence of file or symlink leaves across the subtree, causing folders containing only empty subfolders to flip appearance.

## Notes

Fixed: finalized inventory entries now expose the same subtree-wide empty semantic used by initial tree rendering. A separate descendant leaf count includes files and symlinks while excluding empty directories, and live add/remove updates all ancestors. Regression coverage exercises nested empty directories plus symlink addition/removal.
