---
type: is
id: is-01m7v8ctk4af96q7ykmb5psdd7
title: "Mirror: a pin on a branch follows the branch when a refresh moves it; Refresh replaces the Switch offer"
kind: feature
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m7v8bs62dz0nqmqb9rnhgsdb
created_at: 2026-11-20T01:16:06.627Z
updated_at: 2026-11-20T01:16:06.627Z
---
In mirror (cloud) mode a reader who opened a branch, by URL or the chooser, sees that branch as the mirror last fetched it. When a refresh moves the ref, including a force-push, the server serves the new tip itself and every open page follows. No "X is now at <sha> · Switch" offer.

Design points:
- Record what was selected, apart from the ref label. GitRevisionSubject.ref is set even for a commit pinned by ID ("served under the ref last served"), so add a selection kind (branch, tag, commit, pull) and follow only branch and tag. A commit ID never moves.
- The server switches when MirrorSession._observe_tip finds a branch selection's tip moved after a refresh job ends, under the same _pin_lock, through replace_owned_subject. A ref the origin deleted stays served with the existing "no longer on the origin" line.
- The page follows on its next status poll (pin != shown.pin and the move was a follow): it goes to the same /view/ address on the new pin, or the nearest ancestor that still exists (view_href today falls back to the root). Keep the scroll position and tree expansion where the address survives. A pin_changed refusal caused by a follow repaints and is not an error.
- The foot row stays the freshness label. Clicking it is Refresh: fetch now, then follow. Remove the "switch" offer kind and its copy from source-freshness.js.
- Files and Commits then agree. Today Commits walks ServedMirror.default_tip while Files keeps the old pin.
- Parity: replace the functional row source.newer-revision-offer with a follow row, and update cli-ui-source-freshness.tryscript.md and the status golden.
- Docs to change in the same PR: docs/browsing-history.md, docs/command-line.md, docs/reviewing-pull-requests.md (code part), arch-mirror-acquisition-and-refresh.md, arch-source-sessions-and-pins.md, and the source-pin-guard.js header ("nothing changes under a reader").
