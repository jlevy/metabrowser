---
type: is
id: is-01m7w3mj2y6tpzktkmk8a4ft8k
title: "Ref chooser: tell a repository's own pull requests from a fork's by repository id, not a cached name"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys615s2mfvbc93c9g2pac
created_at: 2026-11-20T09:12:11.613Z
updated_at: 2026-11-20T17:09:34.011Z
---
Senior review A (A7) of PR 651. builtin_plugins/github/pull_catalog.py catalog_heads treats a pull request as the repository's own when its cached head_repository (owner/name, case-insensitive) equals the served repository's name taken from its address. A repository that was renamed or transferred is recorded in pull-request rows under its old name until GitHub's list says otherwise, so its own pull requests read as a fork's and its branch rows show none (tests/test_github_ref_pulls.py pins the behavior). Compare the head repository's id with the catalog's repository_id (the checkpoint keeps it), or the catalog's canonical name, so a rename does not hide them. Needs the head repository's id in the catalog row (PullListRow keeps only head_repository text), so a projection bump and a catalog rebuild.
