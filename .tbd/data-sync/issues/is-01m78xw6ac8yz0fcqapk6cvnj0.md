---
type: is
id: is-01m78xw6ac8yz0fcqapk6cvnj0
title: "PR #383 A3: spec phase 2 text no longer describes what shipped"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m78xvnbykdp66qwvmwnrfzdp
created_at: 2026-11-12T22:25:56.043Z
updated_at: 2026-11-12T23:22:16.384Z
closed_at: 2026-11-12T23:22:16.383Z
close_reason: "Fixed by the spec commit 'plan: record what the layer 4 and phase 2 reviews changed', 277a7065 before the stack #376 rebase and 07c3b2e7 after it (PR #365's branch). It records the Lifetime change from B1, the Collisions deviations, and heldAbove, isTargetLive, and the attachTarget rank under API Changes."
resolution: null
duplicate_of: null
---
Low. PR #383, review A (https://github.com/jlevy/metabrowser/pull/383#pullrequestreview-5882935821). docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md:1092-1093 (Lifetime contradicts B1), 1148-1162 (Collisions lacks the reported deviations: queued malformed input logged, same-element retarget refreshes badges, net covers the queue, facade observes keys), 1230-1236 (API Changes lacks heldAbove, isTargetLive, attachTarget rank). Deferred to the coordinator's single spec-drift commit on PR #365's branch.

## Notes

Deferred to the coordinator's single spec-drift commit on PR #365's branch (docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md); the addressing agent does not edit the spec. Besides review A3's three passages, the spec should record what the PR #383 fixes settled: B1 (8080504f) the Git panel's cancelPending() hands the mounted commit diff to the shell's retained handoff slot, disposed when the next owner's content installs, so Lifetime's 'each host disposes the handle it gets back' now holds for the commit view at that point; B2 (e85218f1) view composition's net runs before the view's own dispose, again after a render resolving after cancellation, and before a failed render's error state; B3 (2f5970d2) the eager queue is a Set and a queued detach() or the pre-load net deletes the entry; abort before load still queued (mb-1cev, waits on the startup-budget re-derivation); A1 (88ca5216) pre-load malformed input is logged under the shortcuts.attach: prefix.
