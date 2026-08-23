---
type: is
id: is-01m0r1a76tq77m6d5g85rphc7n
title: "PR #73 review R3: make compare_builds fail invalid runs"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0r191gatek6ffx1e50wmgr8
created_at: 2026-08-23T19:24:45.145Z
updated_at: 2026-08-23T21:34:06.041Z
closed_at: 2026-08-23T21:34:06.040Z
close_reason: compare_builds now exits nonzero for harness errors, corpus mutation, missing finals, and response differences, with regression tests.
---
PR #73. devtools/compare_builds.py:353-387 records errors, corpus mutation, missing finals, and differences but returns zero unconditionally. Validate the report and fail invalid comparisons. Review: https://github.com/jlevy/metabrowser/pull/73#pullrequestreview-5003175212
