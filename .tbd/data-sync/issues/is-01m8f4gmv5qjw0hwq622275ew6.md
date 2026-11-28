---
type: is
id: is-01m8f4gmv5qjw0hwq622275ew6
title: Reconcile structured views PR 913 with latest main and verify hosted gate
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwhv15ckjw7prckfmmggr
hold: null
hold_until: null
created_at: 2026-11-27T18:33:06.143Z
updated_at: 2026-11-27T19:04:10.149Z
started_at: 2026-11-27T18:33:55.837Z
closed_at: 2026-11-27T19:04:10.147Z
close_reason: Published latest-main root reconciliation; focused gates and exact hosted CI passed; exact guided review verified; PR CLEAN/MERGEABLE and left unmerged as requested.
resolution: null
duplicate_of: null
---
Own PR 913 base layer only: merge latest main preserving root history and formal stack 916, resolve conflicts, validate focused behavior, publish the updated root and exact guided-review pins, and monitor its exact hosted run. Do not modify PR 915 or its worktree; parent owns upper-layer integration. No merge authorization.

## Notes

Completed PR 913 root-only reconciliation. Latest published head f1ca65085bf16a41b8e62e7b8bccd84ab78ac2a3 contains latest main fc79ace6bac718610eb9bf5a6d09cc244ecbc87c; merge parents are 7d262c616711e2c96e4784abc3fb19da9caa25ee and fc79ace6bac718610eb9bf5a6d09cc244ecbc87c. First reconciliation at 7d262c616 against 3741647b3 had full CI success in run 46051181561; main then advanced via PR 912, requiring the second reconciliation. Both had only one manual conflict in docs/project/architecture/arch-parity-registry.md: retain main Markdown diff/link-card owners and the PR relocated static structured-tree owners. All runtime files merged automatically. Ordinary root-only pushes succeeded and worktree is clean. Latest affected pytest selection: 81 passed; six goldens/16 commands passed; executable parity passed (353 declared aspects); all real pre-commit hooks passed with no edits. Initial merge additionally passed complete make lint-check, 124 focused Python tests and four goldens. Latest exact hosted run 46052306963 completed SUCCESS at f1ca65085; gh run watch --exit-status exited 0 and final gh pr checks 913 all required passed, including ci-ok job 140690822551 and every Chrome shard. Final guided-review edit records CI passed; record pins exactly fc79ace6b/f1ca65085 and all five steps/twelve references read ready through production routes. Live PR is CLEAN, MERGEABLE, and not draft. Native stack 916 remains [913,915]. Upper layer owned independently by parent, with no edits, pushes or stack sync by this agent. No merge performed. URLs: https://github.com/jlevy/metabrowser/pull/913 ; https://github.com/jlevy/metabrowser/actions/runs/46052306963 .
