---
type: is
id: is-01m8a64n37rhg7nya1e434qa2y
title: "Stack page: a change notice only for a real change, saying what changed, and a button that redraws"
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/854
    at: 2026-11-25T21:37:35.435Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8806zrnxn9jwj89hffd2yv7
hold: null
hold_until: null
created_at: 2026-11-25T20:25:18.181Z
updated_at: 2026-11-25T21:37:35.437Z
started_at: 2026-11-25T20:25:25.022Z
---
Owner report: on a stack's page the notice "This stack has changed since its comparison was drawn. Show the new comparison" appears a few seconds after the page opens, and clicking Show the new comparison does nothing.

Mechanism (event log 2026-11-25 20:11Z, app runtime b94eb6a): the page drew the stack's first answer while several members' cached records were older than their catalog rows (pending, refreshes in flight). Each member's refresh then landed one at a time, and each moved the comparison's key (a digest of every member's number, merge base, and head), so the page offered a "new" comparison every few seconds. The bottom member's merge base and the top member's head did not move, so the comparison taken drew the same diff as before, and the next member's refresh re-offered within seconds: the click worked but changed nothing visible.

Fix (owner-approved design): (1) catching up is not a change: a newer comparison before the reader interacts is taken silently; (2) no notice for a change that alters nothing visible; (3) the notice says what changed per member (new commits, merged, joined, left); (4) the button redraws at the new comparison and the notice clears, or says the comparison cannot load yet; (5) fix any server-side artifact at its source.
