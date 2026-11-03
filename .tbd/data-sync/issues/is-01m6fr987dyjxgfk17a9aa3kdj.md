---
type: is
id: is-01m6fr987dyjxgfk17a9aa3kdj
title: "PR #284 D4: a render that throws after settleDeferred crashes the failure handler; the file shows nothing and counts as loaded"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fr829v5p0bx9wm4rr3z5wj
hold: null
hold_until: null
created_at: 2026-11-03T03:47:11.724Z
updated_at: 2026-11-03T03:53:09.568Z
started_at: 2026-11-03T03:47:30.605Z
closed_at: 2026-11-03T03:53:09.567Z
close_reason: |
  fixed in f59cebd2: renderDeferred owns a throw past settleDeferred and hydrationHost.fail answers a file it no longer holds; pinned in tests/dom/diff-file-jump-session.js and the jump golden; the reviewer's probe replays with no escape and the failure counted.
resolution: null
duplicate_of: null
---
Medium. src/metabrowser/builtin_plugins/diff/diff-view.js renderDeferred settles the file before createFileState/renderFileBody; a throw there reached hydrationHost.fail, whose lookup found nothing and threw TypeError out of the frame; deferredFailed stayed 0. Same as Qodo https://github.com/jlevy/metabrowser/pull/284#discussion_r4450318509. Review D: https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5746804338. Fix: renderDeferred owns the throw past settleDeferred; hydrationHost.fail answers a file the view no longer holds; pinned in tests/dom/diff-file-jump-session.js.
