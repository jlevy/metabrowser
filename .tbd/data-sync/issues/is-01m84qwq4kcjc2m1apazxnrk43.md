---
type: is
id: is-01m84qwq4kcjc2m1apazxnrk43
title: "PR #758 B1: no test reaches the Back landing's memory write or the same-memory skip beyond chosen, and removing either loses the reader's choice after Back and a reload"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-23T17:40:05.906Z
updated_at: 2026-11-23T17:50:19.901Z
closed_at: 2026-11-23T17:50:19.900Z
close_reason: "Fixed in 086588fbb (#758): github-pull-changes-follow-behavior.js adds a Back step on the production page host (entry A follows a push, a click pushes entry B where a second push is followed and the reader goes back to A's diff, Back restores A's state and calls onHistory, then a reload). Removing land's rememberLanded(), or a same-memory skip comparing only shown.right, fails \"the entry Back lands on remembers the reader's choice\"; with that assertion dropped, the reload draws 8888888."
resolution: null
duplicate_of: null
---
Finding B1 (Medium) of review B (follow-up, round 2) on PR #758 (https://github.com/jlevy/metabrowser/pull/758), at head 44fb44996b9424cb989ff01d17016f2abe97edd9. A test gap in the fix for mb-eg5f; the code is right.

`rememberLanded()` runs at the end of the page handle's `setTab`, `land` and `showFile` (`pull-page.js`). The walk-and-click step in `tests/dom/github-pull-changes-follow-behavior.js` reaches `setTab` (walk) and `showFile` (click) through the production `static/pull-route.js`, but never `land`, which the host calls for Back and Forward (`onHistory`) and for any restore landing. The same-memory skip in `rememberChanges` is pinned only for `chosen`.

Mutations, each in a scratch copy of 44fb449:
- `land` without `rememberLanded()`: the follow session and eight other pull-page and Pulls-tab sessions pass.
- The skip comparing only `shown.right`: the follow session passes.

Probe (the follow session's harness, its hosted production host): entry A follows the first push (9999999, from 85fcb2f); a click on b.py pushes entry B; a second push is followed there (to 8888888) and the reader goes back to 9999999; Back to A restores A's state and calls `host.onHistory`; then a reload on A with the record at 8888888. At 44fb449, A then holds {9999999, chosen} and the reload keeps 9999999 with "The pull request now ends at 8888888. Show the newer changes". With either mutation, A keeps {9999999, from 85fcb2f, not chosen}, and the reload draws 8888888 with the note "The pull request's head moved from 9999999 to 8888888", so the reader's choice is lost.

Fix: add a Back step to the walk-and-click step: keep the entry the page was on before the click, restore it as a same-document traversal does (`window.history.state` set to that entry's saved state, address back), call the hosted host's `onHistory`, then assert the entry's memory and the reload. Build it as in the probe, with the chosen diff at the same head the earlier entry shows, so a skip that compares only `shown` fails too. Optionally name Back in `changelog.d/mb-eg5f.md`, since 44fb449 fixes it as well.
