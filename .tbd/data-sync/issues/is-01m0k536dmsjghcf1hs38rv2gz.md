---
type: is
id: is-01m0k536dmsjghcf1hs38rv2gz
title: Say which population the type distribution counts
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
hold: null
hold_until: null
created_at: 2026-08-21T21:54:37.107Z
updated_at: 2026-11-04T17:14:29.837Z
started_at: 2026-11-01T16:05:49.733Z
closed_at: 2026-11-04T17:14:29.837Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
The type distribution in File Overview counts against a population the reader has to infer, and two people in one session inferred it wrong.

The three tally rows are fixed populations, and the distribution below follows Show ignored. So the distribution's percentages match exactly one of the tracks above it, and which one changes with the checkbox: Total while Show ignored is on, Files while it is off. Nothing on screen says so, and the numbers are all internally consistent, so the mismatch reads as a defect rather than as two populations.

Measured on this repository with Show ignored off: the distribution reports JavaScript at 25.9%, which is the Files track's 25.93% and not the Total track's 43.71%. Turn the checkbox on and the correspondence moves to Total at 24.95%.

Say it rather than leaving it to be worked out. A caption on the distribution naming its population and count — "Share of Total (8,533 files)" against "Share of Files (536 files)" — switching with the checkbox, is one line and removes the ambiguity. Marking the matching tally row is the alternative and is probably weaker: it needs a visual treatment that does not read as selection.

Whichever is chosen, the caption is the accessible answer too: the correspondence is currently available only by comparing numbers across two tables.

## Notes

2026-11-01: fixed in PR #275, open, CI green at its last read. Close when it merges; its required review has not run.
