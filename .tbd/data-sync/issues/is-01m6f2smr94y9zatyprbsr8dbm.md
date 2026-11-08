---
type: is
id: is-01m6f2smr94y9zatyprbsr8dbm
title: "PR #275 A4: Treemap on a not-indexed folder asks for a rollup and gives no reason"
kind: task
status: in_progress
priority: 2
version: 4
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6ezt071eh0dj86tf6rct9w6
created_at: 2026-11-02T21:31:40.168Z
updated_at: 2026-11-08T18:09:37.573Z
---
Low, optional suggestion A4 on PR #275 (review https://github.com/jlevy/metabrowser/pull/275#pullrequestreview-5743293650), deferred there. On a not_indexed folder the Treemap tab mounts the rollup controls, requests /api/rollup, gets the 404, logs a console warning on every visit, and shows 'Treemap unavailable.' without the reason File Overview gives. ctx.raw already carries dir.not_indexed. Doing it: share the statement out of file-overview-panel.js, add a branch in renderTreemap that keeps the parent control and asks for nothing, cover it in a session, and add a clause to the CHANGELOG. Waits on a decision whether this goes before the tag.

## Notes

November 8: root selected this small UI correction before the tag under the owner's instruction to resolve remaining easy stabilization/review items. Read-only proposal: mb-o12l-readonly-proposal-20261108/proposal.txt and proposal-production.patch in private release evidence. Reuse the exact existing Overview explanation via already-loaded folder-totals.js; return before rollup/watch/control resources for only the supported hidden/symlink not_indexed reasons; keep public parent navigation and disposal. Ordinary and pinned folders keep their current behavior. Add a focused production-session/golden with zero request/resource assertions, retaining positive controls and existing Overview wording.

Implementation is queued until the frozen exact426 DATA and corrected full browser comparison return ownership. No source, branch, fixture or dependency change has occurred. Root will implement in a separate reviewed PR, then reconcile draft QA #336 with forward merges and correct bases/ancestry; never rebase or force-push. The final new build requires focused and full verification, CI, installation and manual evidence. This is independent of paused future Files workflow mb-itzy.
