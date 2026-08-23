---
type: is
id: is-01m0pna9mf444e07mx8mvh9ch9
title: Conflated the browser two /api/tree requests, twice, in opposite directions
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:50.286Z
updated_at: 2026-08-23T07:24:19.084Z
---
Two errors here, not one, and the second was made while correcting the first. That is why this bead is worth keeping.

THE FACTS, established by reading tree.py and app.js rather than inferring from payloads. The browser makes TWO different /api/tree requests:

- ROWS: `/api/tree` with no depth parameter. `_tree_depth_from_query` resolves an absent depth to `DEFAULT_TREE_DEPTH = 2` (tree.py:49). This is what the file tree renders from.
- TALLIES: `/api/tree?depth=0`, polled behind the render by `scheduleRootSummaryRefresh` (app.js:1032). It returns `tree: []` -- zero rows, by design -- and carries `summary`, `extensions`, `type_families` and the rest.

ERROR ONE. The equivalence check polled depth=2, saw seven tally fields populated on v0.6.0 and null on the candidate, and reported a regression. It is deliberate: since #66 only depth=0 computes tallies, and server.py:1565 says so in as many words -- every tally field in that payload is nullable and guarded field-by-field on the client, so a row request arriving without them is a shape the browser already handles.

ERROR TWO, the one worth the bead. Correcting error one, I wrote that the browser fetches depth=0 and therefore always uses the channel that computes tallies, and characterised depth=2 as a channel nobody uses. That is backwards. depth=2 IS the browser row channel -- the single most frequent request in the application. The correct statement: the browser uses BOTH, depth=2 for rows and depth=0 for tallies, and the row request stopped carrying tallies it never needed.

WHY THE SECOND ERROR WAS EASY. Both come from assuming one endpoint is "the" client endpoint. The two payloads carry the same twelve keys and differ only in which are populated, so nothing in a response distinguishes a rows request from a tallies request. Only the caller does.

THE FIX, now in the comparison harness: name both endpoints as separate constants, say in the comment what each is for and which client code issues it, poll ROW_ENDPOINT for anything about rows, and compare both in the final equivalence. A harness with a single CLIENT_ENDPOINT constant is one that will make this mistake again.

MEASUREMENT CONSEQUENCE. Time-to-first-row cannot be measured on depth=0 at all, because depth=0 returns no rows ever. An early harness version reported first_row as null for every run, and the null was correct.

## Notes

FIXED in #73 on both sides. In the harness, ROW_ENDPOINT and TALLY_ENDPOINT are separate named constants, each with a comment saying what it is for and which client code issues it, and the final equivalence compares both. In the documentation, arch-state-and-delivery.md now carries the table stating which depth answers which question. The single CLIENT_ENDPOINT constant that made this error possible is gone.
