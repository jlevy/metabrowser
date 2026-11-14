---
type: is
id: is-01m0dmjdzed5x4sfnzvad9q3p7
title: "Patch emitter: ChangeSetDocument to git-applyable unified patch text"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T18:29:38.391Z
updated_at: 2026-11-14T18:43:37.020Z
---
Backward compatibility is bidirectional: we parse existing patch formats, so we must also write them. Emit git-extended unified patch text from a hydrated document — diff --git headers, rename/copy plus similarity, mode lines, /dev/null, C-quoted non-UTF-8 paths, no-newline markers — such that git apply accepts it against the base tree. Round-trip is the test: parse(emit(document)) equals document for text changes, and emit output applied by git reproduces the target tree the oracle already verifies. Corpus-able: add emit cases beside apply cases. Binary payload scope follows docs/project/research/research-2026-08-19-file-patch-formats.md; file-diff-format.md names this emitter as tracked work.
