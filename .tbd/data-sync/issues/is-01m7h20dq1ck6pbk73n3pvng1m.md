---
type: is
id: is-01m7h20dq1ck6pbk73n3pvng1m
title: "PR #449 B6: two processes is not the floor for a commit click; one git log -1 run is"
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7h1z1rnzfafwf740k7yrzdh
created_at: 2026-11-16T02:12:04.448Z
updated_at: 2026-11-16T02:53:37.654Z
---
Deferred from review B of PR #449 (B6, https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914053530): a later hypothesis, not this PR. One git log -1 --no-show-signature --format=%H%x00%P%x00 run with the one run's options prints the commit, its parents, then the listing and patch, so a commit click could take one Git process. It needs its own byte-for-byte guard covering root commits and shallow boundaries (--root, recorded_parents), configuration only log reads (log.showSignature, log.showRoot, log.follow), a revision read as a path (end with --), and the configuration cases of A2 and A3; on a store the cat-file --batch-command pool could resolve <rev>^{commit} and its parent without a spawn. Waits on H116 (exp-096) being decided.
