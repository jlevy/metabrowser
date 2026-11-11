---
type: is
id: is-01m74w0wrmggjkde2vb7k0w952
title: "PR #348 C2: sharing a GraphQL launch relies on a text-prefix read-only check"
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
created_at: 2026-11-11T08:36:35.220Z
updated_at: 2026-11-11T09:24:58.293Z
started_at: 2026-11-11T09:24:55.997Z
closed_at: 2026-11-11T09:24:58.292Z
close_reason: "Fixed in a4d724fb: sharing removed; gh_graphql lexes the document and admits exactly one query operation plus fragments, refuses query/operationName variable names. tests/test_github_gh_process.py."
resolution: null
duplicate_of: null
---
Low. gh.py:583, 588, 300-364. Review C https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855484116
