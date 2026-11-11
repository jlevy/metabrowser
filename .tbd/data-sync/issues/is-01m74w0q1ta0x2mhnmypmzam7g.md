---
type: is
id: is-01m74w0q1ta0x2mhnmypmzam7g
title: "PR #348 A7: inherited descriptors and shared manifest loads untested"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:29.369Z
updated_at: 2026-11-11T09:24:56.677Z
started_at: 2026-11-11T09:24:55.894Z
closed_at: 2026-11-11T09:24:56.676Z
close_reason: "Fixed: c5fc056d..e190083a. test_staging_writers_inherit_the_entry_lease_and_not_the_reservation (5eb97c03) records each staging Git command's descriptors; test_preparation_and_a_reader_share_one_manifest_computation (e190083a) overlaps preparation and a reader, one computation; mutation-checked."
resolution: null
duplicate_of: null
---
Medium. acquire.py:468-473; pull_manifest.py:207-226. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600
