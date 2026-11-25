---
type: is
id: is-01m88z29pn3zaqj6vwwt06kjx8
title: "Branch menu: choosing Working tree on a local checkout does not switch the view; make working tree vs viewing another branch clear"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T09:02:26.515Z
updated_at: 2026-11-25T09:02:26.515Z
---
Reported by the user on a local checkout whose working tree is on a feature branch. The Files tab's branch control shows the branch name. Choosing 'Working tree' in the branch menu does not switch the view (it seems to stay on the branch view), so it feels like a bug. Wanted: a local folder opens on its working tree by default; the control makes clear that you are viewing the working tree, which happens to be on branch X (we never modify the working tree, we only show what is there). Choosing another branch or a remote ref switches the view away from the working tree, and that state must look clearly different, with an obvious way back. Investigate the current behavior and any related bugs first.
