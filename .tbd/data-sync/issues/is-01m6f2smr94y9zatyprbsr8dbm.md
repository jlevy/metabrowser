---
type: is
id: is-01m6f2smr94y9zatyprbsr8dbm
title: "PR #275 A4: Treemap on a not-indexed folder asks for a rollup and gives no reason"
kind: task
status: in_progress
priority: 2
version: 6
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6ezt071eh0dj86tf6rct9w6
created_at: 2026-11-02T21:31:40.168Z
updated_at: 2026-11-08T20:46:03.494Z
---
Low, optional suggestion A4 on PR #275 (review https://github.com/jlevy/metabrowser/pull/275#pullrequestreview-5743293650), deferred there. On a not_indexed folder the Treemap tab mounts the rollup controls, requests /api/rollup, gets the 404, logs a console warning on every visit, and shows 'Treemap unavailable.' without the reason File Overview gives. ctx.raw already carries dir.not_indexed. Doing it: share the statement out of file-overview-panel.js, add a branch in renderTreemap that keeps the parent control and asks for nothing, cover it in a session, and add a clause to the CHANGELOG. Waits on a decision whether this goes before the tag.

## Notes

November 8 implementation: a focused production-module session first fails because a known excluded folder acquires rollup controls. The fix shares the existing Overview reason in folder-totals.js and returns before any rollup/control/watch resources, retaining parent navigation and idempotent cleanup. Hidden and symlink sessions now pass; repeated mounts dispose listeners. Existing ordinary/scanning/refused/capped folder behavior and Overview session remain passing. Four focused pytest cases, both golden sessions, functional parity and both browser type targets pass. Independent code review is in progress. Original pre-fix and new evidence are separate under mb-o12l-readonly-proposal-20261108. This is not yet committed, PR-qualified or installed.

November 8, final c3 delivery (merge pending): PR #337 at c3d093d2d222ddce74568e7c74111e2cc0c57d3f passed normal-hook full make verify in 1438.51 seconds: 4929 Python passes, nine expected skips and 388 goldens, with lint/types, both audits, distribution and installed-wheel smoke checks; filesystem observer zero bytes. All nine PR CI jobs passed in workflow 42518226853. Exact wheel 0.11.1.dev1290+c3d093d2d is installed for both aliases and all three retained previews, with eleven healthy plugins, 45 unchanged pins and 45 served-asset comparisons. Independent reviews A/B/C cover the fixes and D covers the comment-only startup correction; the 175 KB budget remains unchanged. Original failed gate and 426 comparison evidence remain preserved. No merge, quiet performance or owner release acceptance is claimed. Keep this bead open until root reconciles the actual merge. Public references: https://github.com/jlevy/metabrowser/pull/337 and https://github.com/jlevy/metabrowser/actions/runs/42518226853.

Installed built-in-browser hidden and symlink descendant cases pass with the same Overview/Treemap reason; parent navigation keeps Treemap selected. The normal Unicode root renders its actual cells. The focused full-module session verifies excluded folders allocate no rollup/control/watch resources; manual network counts were not instrumented.
