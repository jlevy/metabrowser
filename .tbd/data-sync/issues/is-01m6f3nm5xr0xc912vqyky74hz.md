---
type: is
id: is-01m6f3nm5xr0xc912vqyky74hz
title: Re-run the folder comparison after this branch merges
kind: task
status: in_progress
priority: 1
version: 4
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-02T21:46:57.084Z
updated_at: 2026-11-03T15:35:21.619Z
started_at: 2026-11-03T09:32:28.834Z
---
This branch changes plain-folder narrow diffs, and possibly toggles. Extends mb-2g6f's re-run on the head to be tagged; the sign-off record must then name this branch's changes too.

## Notes

Review A of PR #284 (A6): include a commit of more than 50 files in the plain-folder re-run. On a folder nothing is kept, so each deferred file costs the manifest run again (about 0.7 s at 1,183 files), one after the other; the scheduler's one-at-a-time hydration is a folder-visible change beside the narrow diffs and toggles.

2026-11-03 owner clarification: this is a new feature stack whose frontend and backend ship together on one local server; there are no old-client backward-compatibility constraints. Earlier interpretation of additive as preserving omitted-number PR calls was too broad. Compatibility-only API aliases and the extra dotenv expansion resolver have been forward-reverted, without rewriting history. #280 ed400452 is tree-identical to reviewed64fa; #281 a30750dc restores required numbers with focused current-contract tests. Final clean composition de87065ded8a606f21fb85093474c8ca0cc50cbe has its entire src tree exactly equal measured/reviewed68db82b5 (treeca658425530ac05b2202ba7f9d223ade08fbd9f4), preserving all G1/cache/recovery/navigation/rendering fixes. All live frontend and CLI calls/current runnable examples supply explicit numbers. Root focused148tests passed147.07seconds; full exact-head verification, independent composition audit, Chrome smoke and public live checks are in progress. R6 ed0 full makeverify passed before this policy clarification and is retained as superseded evidence. The complete945 diagnostic run (20527data/1320browser/120file/three connectionpairs) is preserved NONFINAL, not a backward-compatibility gate or owner-signoff requirement for new PR API shapes. No source branches pushed yet beyond earlier font64fa; no PR merged; all merges forward; original WIP and8863 untouched.
