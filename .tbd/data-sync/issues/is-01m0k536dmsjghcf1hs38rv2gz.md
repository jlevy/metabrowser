---
type: is
id: is-01m0k536dmsjghcf1hs38rv2gz
title: Say which population the type distribution counts
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-21T21:54:37.107Z
updated_at: 2026-08-21T21:54:37.107Z
---
The type distribution in File Overview counts against a population the reader has to infer, and two people in one session inferred it wrong.

The three tally rows are fixed populations, and the distribution below follows Show ignored. So the distribution's percentages match exactly one of the tracks above it, and which one changes with the checkbox: Total while Show ignored is on, Files while it is off. Nothing on screen says so, and the numbers are all internally consistent, so the mismatch reads as a defect rather than as two populations.

Measured on this repository with Show ignored off: the distribution reports JavaScript at 25.9%, which is the Files track's 25.93% and not the Total track's 43.71%. Turn the checkbox on and the correspondence moves to Total at 24.95%.

Say it rather than leaving it to be worked out. A caption on the distribution naming its population and count — "Share of Total (8,533 files)" against "Share of Files (536 files)" — switching with the checkbox, is one line and removes the ambiguity. Marking the matching tally row is the alternative and is probably weaker: it needs a visual treatment that does not read as selection.

Whichever is chosen, the caption is the accessible answer too: the correspondence is currently available only by comparing numbers across two tables.
