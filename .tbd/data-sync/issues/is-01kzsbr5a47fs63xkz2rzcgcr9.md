---
type: is
id: is-01kzsbr5a47fs63xkz2rzcgcr9
title: "PR #24: human visual validation pass of the Git graph"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/done/plan-2026-08-06-git-graph-view.md
labels: []
dependencies: []
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-11T21:30:40.323Z
updated_at: 2026-11-04T17:14:17.845Z
closed_at: 2026-11-01T16:21:21.235Z
close_reason: "PR #24 closed as consolidated into #58 and the Git panel has shipped since, so the PR-title goal no longer exists. No human sign-off of graph lanes was ever recorded; if one is wanted it belongs in the release walkthrough."
resolution: canceled
duplicate_of: null
extensions:
  linear:
    id: 76eb6a23-1ca4-4b82-b473-18f5a660afd6
    linked_at: 2026-08-16T08:05:43.447Z
---
The last engineering gap on the Git graph branch. Everything else is automated-green; graph *proportions* have never had a human sign-off, which is why the PR is still titled a spike.

Checklist (from the PR body):
- metab . in a repository: Git tab appears, lanes sensible, badges on the right commits, HEAD ring on the checked-out commit.
- Lane colours and columns stay continuous across the 250-row paging boundary; no jump.
- Hover a row: full message and 'files changed / +N -N' card after ~300ms. Click: detail view. Click a changed file: file opens.
- Light and dark themes: lanes legible, badges readable, hollow HEAD ring matches the row background in default, hover, AND selected states (the selected case is new in R16).
- Non-repository directory: no Git tab, no console errors. Repository subdirectory: files outside the served root listed but inert.
- Fresh git init with no commits: 'No commits yet', not an error.
- New since the #30 merge: the filter bar is hidden under the Git tab and restored on return, and the Refresh button now carries the .btn family focus ring.

When this passes, drop 'spike: needs visual validation' from the PR title.
