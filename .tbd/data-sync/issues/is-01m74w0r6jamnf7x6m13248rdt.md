---
type: is
id: is-01m74w0r6jamnf7x6m13248rdt
title: "PR #348 A10: user docs still say Metabrowser never reads a token"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:30.545Z
updated_at: 2026-11-11T09:24:57.326Z
started_at: 2026-11-11T09:24:55.915Z
closed_at: 2026-11-11T09:24:57.325Z
close_reason: "Fixed in a4d724fb: the gh in-flight wrapper and its GH_TOKEN/GITHUB_TOKEN read are removed (A5), so 'Metabrowser never reads or stores a token' in docs/reviewing-pull-requests.md and docs/command-line.md is true again; gh.py's docstring says so."
resolution: null
duplicate_of: null
---
Low. docs/reviewing-pull-requests.md:253; docs/command-line.md:363; gh.py:287, 300-341. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600
