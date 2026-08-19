---
type: is
id: is-01m0dmjdzed5x4sfnzvad9q3p7
title: "Patch emitter: ChangeSetDocument to git-applyable unified patch text"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-19T18:29:38.391Z
updated_at: 2026-08-19T18:29:38.391Z
---
Backward compatibility is bidirectional: we parse existing patch formats, so we must also write them. Emit git-extended unified patch text from a hydrated document — diff --git headers, rename/copy+similarity, mode lines, /dev/null, C-quoted non-UTF-8 paths, no-newline markers — such that git apply accepts it against the base tree. Round-trip is the test: parse(emit(document)) equals document for text changes, and emit output applied by git reproduces the target tree the oracle already verifies. Corpus-able: add emit cases beside apply cases. Scope-limited by research findings (mb research bead) for binary payloads.
