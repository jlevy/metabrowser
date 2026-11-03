---
type: is
id: is-01m6h9774ejbxc15dh0d3h4njk
title: Disposition exact checkout CLI status-line assertion
kind: bug
status: closed
priority: 2
version: 4
delegate: checkout_design
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
hold: null
hold_until: null
created_at: 2026-11-03T18:02:25.293Z
updated_at: 2026-11-03T20:17:10.560Z
started_at: 2026-11-03T18:06:54.049Z
closed_at: 2026-11-03T20:17:10.560Z
close_reason: Review disposition completed and published, with independent controls supporting the rebuttal or decline. The reviewer-visible threads remain open; this closure records completed triage rather than an unimplemented source fix. Final stack gates passed at ea771741; no PR merged.
resolution: null
duplicate_of: null
---
Review newline-sensitive assertion against the deliberate CLI transcript wire contract; change only if this is a genuine test defect. GitHub review: https://github.com/jlevy/metabrowser/pull/288#discussion_r4458533495

## Notes

2026-11-03: Coordinator approved rebuttal of Qodo discussion_r4458533495. The POSIX checkout test uses _api -> run_metab -> in-process StringIO. The exact status: 409 newline is the deliberate CLI status-line boundary, not a platform newline assumption; the response JSON is independently parsed and asserted. Independent reviewer agrees. No source or expectation change; leave the GitHub thread visible. Publication and final closure remain with the coordinator; no sync performed.
