---
type: is
id: is-01m8f4gmv5qjw0hwq622275ew6
title: Reconcile structured views PR 913 with latest main and verify hosted gate
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwhv15ckjw7prckfmmggr
hold: null
hold_until: null
created_at: 2026-11-27T18:33:06.143Z
updated_at: 2026-11-27T18:52:45.303Z
started_at: 2026-11-27T18:33:55.837Z
---
Own PR 913 base layer only: merge latest main preserving root history and formal stack 916, resolve conflicts, validate focused behavior, publish the updated root and exact guided-review pins, and monitor its exact hosted run. Do not modify PR 915 or its worktree; parent owns upper-layer integration. No merge authorization.

## Notes

PR 913 root only reconciled twice as main advanced. First published merge 7d262c616711e2c96e4784abc3fb19da9caa25ee integrated main 3741647b399e726747e385d456573c54b1f458b0; full exact CI run 46051181561 passed, including ci-ok and all six Chrome shards. Main then advanced to fc79ace6bac718610eb9bf5a6d09cc244ecbc87c (PR 912). Latest published root is f1ca65085bf16a41b8e62e7b8bccd84ab78ac2a3, with parents 7d262c616 and fc79ace6b. Both merges had only the same parity-registry conflict: retain main Markdown diff/link-card owners and the structured-tree owners moved to static by this PR. Runtime files merged automatically. Latest affected validation: 81 Python tests passed, six golden files/16 commands passed, parity passed with 353 functional aspects, and all real pre-commit hooks passed without edits. Initial merged root also passed complete make lint-check and 124 focused tests/four goldens. No dependency duplication or upper-layer branch edits. Native stack 916 preserved; ordinary root-only pushes used. Latest exact CI run 46052306963 is queued/running; parent owns PR 915 integration. Guided-review pins refreshed through actual record and production routes. No merge performed.
