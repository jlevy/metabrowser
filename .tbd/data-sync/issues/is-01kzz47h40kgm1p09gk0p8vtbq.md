---
type: is
id: is-01kzz47h40kgm1p09gk0p8vtbq
title: "PR #35 review R6: recursive expand still resyncs per folder"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzz46ttyre78pjmkxynpfh3z
created_at: 2026-08-14T03:14:41.920Z
updated_at: 2026-08-14T03:32:03.357Z
closed_at: 2026-08-14T03:32:03.357Z
close_reason: "Fixed in 78ee53e: expandAllDescendants and the recursive branch of toggleTreeFolder pass synchronize:false, matching collapse."
---
collapseAllDescendants passes {synchronize:false} but expandAllDescendants does not, so a Shift+activate expand runs a full visible-row repair per descendant folder plus one per lazy subtree load. Mirror of the collapse fix already applied for the Bugbot finding.
