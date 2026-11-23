---
type: is
id: is-01m7v8cv4e6sjryervx72qmn90
title: "Folder mode: a revision of a checkout's branch follows that branch when the checkout's refs move; the working tree stays the working tree"
kind: feature
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7v8bs62dz0nqmqb9rnhgsdb
hold: null
hold_until: null
created_at: 2026-11-20T01:16:07.181Z
updated_at: 2026-11-23T06:55:05.401Z
started_at: 2026-11-23T06:55:05.398Z
---
In a repository folder, the working tree is live through the watcher. A branch chosen in the Files chooser (a local branch, or a remote-tracking branch such as origin/main) shows that branch's last commit and should follow it when it moves: the reader commits, or a fetch moves origin/main. Today arch-source-sessions-and-pins.md, Revisions of a Checkout, lists this under Not yet ("a branch that moves while it is shown is not followed").

- Detect a move by reading refs, never by fetching. The checkout's ref-state fingerprint behind the refs memo is the cheap signal. A checkout's page has no status poll today, so add one, or tie it to the existing watcher, whichever measures cheaper.
- Follow the same way as the mirror (the sibling bead): same /view/ address on the new commit, or the nearest ancestor that exists.
- A commit ID and Working tree never move.
- The read-only rule holds: nothing is written into the checkout.

## Notes

2026-11-22 check: still not built. On main, arch-source-sessions-and-pins.md (Revisions of a Checkout) still lists 'a branch that moves while it is shown is not followed' under Not yet. Not blocked on either decision: following refs the reader's own commit or fetch moved needs no fetch by Metabrowser (mb-gkq1).
