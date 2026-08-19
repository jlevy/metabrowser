---
type: is
id: is-01m0djs7390byzsbbq4hgzapqq
title: "Diff: anchor a patch file against a repository revision"
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T17:58:23.592Z
updated_at: 2026-08-19T17:58:23.592Z
---
The missing bridge the context question exposes: a bare patch is context-blind (kind: patch snapshots, empty content refs), while the apply oracle already IS the context validator — it replays hunks against a base tree and refuses precisely. Add the marrying surface: --diff file.patch --against REV (and the equivalent option in the document hook) resolves each old side by path at REV, runs apply, and annotates each FileChange with anchored/clean/conflicted plus real content refs — upgrading a foreign patch into an anchored comparison with Before/After and context expansion available. Two validation levels: index-line oid precheck when the patch carries oids, full hunk replay always. git apply --check semantics, through the model.
