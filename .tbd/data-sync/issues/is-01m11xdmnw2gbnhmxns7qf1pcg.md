---
type: is
id: is-01m11xdmnw2gbnhmxns7qf1pcg
title: "PR #31 review R10: status argv restates hardening the shared runner applies"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:29:07.259Z
updated_at: 2026-08-27T15:44:29.032Z
closed_at: 2026-08-27T15:44:29.031Z
close_reason: "Fixed in dbe3206: argv now shows <common-hardening-args> and notes _COMMON_ARGS already supplies both flags and that core.quotepath is inert under -z."
resolution: null
duplicate_of: null
---
plan-2026-08-26-git-status-and-working-tree-diffs.md:246-247. --no-optional-locks and core.quotepath=false are already in _COMMON_ARGS (git/process.py:56); core.quotepath is a no-op under -z.
