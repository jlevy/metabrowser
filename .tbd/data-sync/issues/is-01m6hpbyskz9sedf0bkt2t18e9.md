---
type: is
id: is-01m6hpbyskz9sedf0bkt2t18e9
title: Distinguish an empty Open filter from a repository with no PRs
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
created_at: 2026-11-03T21:52:12.077Z
updated_at: 2026-11-03T21:52:12.077Z
---
Independent landing probe found followLanding defaults its GET toOpen, while describeLanding treated fetched0 plus complete as repository-wide absence. A repository with zeroOpen and17Closed PRs therefore said No pull requests even on the Closed landing. Use exact repository_total for repository absence, or explicitly name the selected empty filter; preserve closed/all navigation without falsely claiming the repository is empty.
