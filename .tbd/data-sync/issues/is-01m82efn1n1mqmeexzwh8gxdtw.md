---
type: is
id: is-01m82efn1n1mqmeexzwh8gxdtw
title: Retry a cache lock open after concurrent staging cleanup
kind: bug
status: in_progress
priority: 1
version: 3
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45064439324/job/137337320471
    at: 2026-11-22T20:17:18.474Z
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-22T20:17:11.721Z
updated_at: 2026-11-22T20:17:18.490Z
---
Main CI run 45064439324, job 137337320471, failed test_two_opens_of_an_old_home_at_once_migrate_it_once[f01]. Two cache opens can sweep the same abandoned staging entry. A normal sweep can remove the staging lock between inspection and opening it, causing a create-capable open to return FileNotFoundError. Preserve the existing bounded retry and the no-create behavior.
