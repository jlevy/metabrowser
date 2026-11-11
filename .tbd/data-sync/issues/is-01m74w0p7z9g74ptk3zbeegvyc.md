---
type: is
id: is-01m74w0p7z9g74ptk3zbeegvyc
title: "PR #348 A5: gh in-flight wrapper lacks the spec's measurement, does nothing for stored logins"
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
created_at: 2026-11-11T08:36:28.542Z
updated_at: 2026-11-11T10:57:52.538Z
started_at: 2026-11-11T09:24:55.881Z
closed_at: 2026-11-11T10:57:52.538Z
close_reason: "Fixed: a4d724fb (measured 3 of 1,523 overlapping launches across 440 server-flow tests; wrapper removed) and 9163be07 (pulls-tab plan records the measurement and status)."
resolution: null
duplicate_of: null
---
Medium. gh.py:279-365, 307, 35-36; plan-2026-10-01-github-pulls-tab.md:637. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600
