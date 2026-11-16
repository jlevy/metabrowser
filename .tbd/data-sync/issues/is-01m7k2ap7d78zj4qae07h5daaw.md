---
type: is
id: is-01m7k2ap7d78zj4qae07h5daaw
title: Retake screenshot-commits.jpg and screenshot-pull-request.jpg after the header parity layer (mb-26zj) lands
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7hgpct6qpjeqfpyetf79fef
created_at: 2026-11-16T20:56:09.708Z
updated_at: 2026-11-16T20:56:09.708Z
---
From PR #452 review B2 (https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5927467914). images/screenshot-commits.jpg shows the old change-stats rows ('1 M file / +4 -1 lines'), and images/screenshot-pull-request.jpg shows branch chips in Pulls rows, branches on the author's line, and no Diff summary row; both predate #446. mb-26zj changes both the commit page's and the pull request page's headers, so retaking now would date them again. Retake both at a head that contains mb-26zj, and check their alt text and the guides beside them (docs/browsing-history.md, docs/reviewing-pull-requests.md) still match.
