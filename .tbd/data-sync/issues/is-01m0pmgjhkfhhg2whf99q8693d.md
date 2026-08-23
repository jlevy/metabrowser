---
type: is
id: is-01m0pmgjhkfhhg2whf99q8693d
title: Depth-capped /api/tree no longer computes navigation tallies
kind: task
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:21:47.429Z
updated_at: 2026-08-23T07:12:44.794Z
---
Recorded from the side-by-side validation of #66 (mb-j7xx): the one behaviour difference between v0.6.0 and main. It is DELIBERATE, documented in code at server.py:1565, and filed because an API client can observe it and the release notes do not mention it.

CORRECTED DESCRIPTION. An earlier version of this bead said the browser fetches depth=0 and so always uses the channel that computes tallies. That understates what changed. The browser makes two requests:

- Rows: `/api/tree` with no depth, resolved by the server to `DEFAULT_TREE_DEPTH = 2`. This is the file tree own request, and it is the one that lost its tallies.
- Tallies: `/api/tree?depth=0`, polled behind the render by `scheduleRootSummaryRefresh` (app.js:1032), returning `tree: []` plus the tally fields.

So this is not a change to an unused channel. It is a change to the application most frequent request, made safe by the client fetching tallies separately and guarding each field. See sibling mb-hr8o for how that distinction was got wrong twice.

WHAT CHANGED. `summary`, `extensions`, `canonical_extensions`, `file_type_registry`, `type_families`, `type_presets` and `recency_tallies` are no longer computed for a depth-capped request. A depth>=1 request serves them only from a fresh memo and returns null otherwise.

MEASURED. On a frozen corpus, `/api/tree?depth=0` shows zero differences between the builds. On a live tree polling only depth=2: baseline 7/7 tally fields populated, candidate 0/7, then 7/7 after any single depth=0 request. On a 247,153-file project corpus both builds report identical rows, files and bytes.

WHY IT WAS DONE, from the server own comment: the tally pass costs 0.37s at 60,000 files indexed and 1.30s at 220,000, and it competes with the walker -- exp-005 measured watching a scan slowing it twelvefold. exp-007 records srv_scanning_ms 311ms -> 2ms.

WHAT TO DECIDE. Whether the /api/tree documentation states which depths compute tallies, and whether the release notes for #66 mention it. Nothing in the code needs to change; the trade is measured and sound. This is about a reader of the API being able to find it out without reading server.py.

## Notes

DONE in #73. Both questions this bead posed are answered.

API documentation: arch-state-and-delivery.md now carries a table under the route list stating that /api/tree answers two different questions, which depth selects each, what each returns, and which client code issues it -- including that an absent depth resolves to DEFAULT_TREE_DEPTH = 2, so the browser's ordinary row request is a depth-2 request, and that depth=0 never carries rows so time-to-first-row cannot be measured on it.

Release notes: CHANGELOG has it under Unreleased, in the section for what a plugin author can observe, with the reason and a pointer to the route documentation.

No code changed. The trade is measured and sound; this was only ever about a reader of the API being able to find it out without reading server.py.
