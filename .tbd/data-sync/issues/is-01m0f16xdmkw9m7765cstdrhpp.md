---
type: is
id: is-01m0f16xdmkw9m7765cstdrhpp
title: "Diff: one tree materializer, batched blob reads"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:29:46.931Z
updated_at: 2026-08-20T07:29:46.931Z
---
PR #58 review S3 (deferred): diff_cli._materialize and tests/diff_fixture_repo.materialize_tree are near-duplicate ls-tree parsers (async vs sync transport); share one prod implementation and consider git cat-file --batch so --diff-check stops spawning one subprocess per blob.
