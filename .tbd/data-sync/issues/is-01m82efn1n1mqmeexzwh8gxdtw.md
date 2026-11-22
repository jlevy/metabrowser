---
type: is
id: is-01m82efn1n1mqmeexzwh8gxdtw
title: Retry a cache lock open after concurrent staging cleanup
kind: bug
status: in_progress
priority: 1
version: 7
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45064439324/job/137337320471
    at: 2026-11-22T20:17:18.474Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/697
    at: 2026-11-22T20:23:05.196Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45066092764/job/137345121178
    at: 2026-11-22T20:33:20.116Z
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-22T20:17:11.721Z
updated_at: 2026-11-22T20:33:20.679Z
---
Main CI run 45064439324, job 137337320471, failed test_two_opens_of_an_old_home_at_once_migrate_it_once[f01]. Two cache opens can sweep the same abandoned staging entry. A normal sweep can remove the staging lock between inspection and opening it, causing a create-capable open to return FileNotFoundError. Preserve the existing bounded retry and the no-create behavior.

## Notes

Candidate a2e1a4831b26237b3ab297035b2bf78de0d82003 is based on exact failing main 0e4e627e64706aeeb3e08d3feb234b64cb16ed2f. The deterministic create-capable regression failed with FileNotFoundError on the base while its no-create control passed. With the bounded O_CREAT-only retry, permissions, locks, and concurrent migration suites passed locally with 479 passes and one skip. Normal pre-commit passed. Exact hosted CI 45066092764 passed on attempt 1. The ci-ok job 137345121178 recorded main-red run=45064439324 head=0e4e627e64706aeeb3e08d3feb234b64cb16ed2f tested=yes.
