---
type: is
id: is-01m0c4cc698vj8c0qmfvtw24ad
title: "diff/apply.py: the apply oracle"
kind: feature
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01kxse0v48bnzvcya9vpxh4s06
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:27:28.329Z
updated_at: 2026-08-19T04:51:08.644Z
closed_at: 2026-08-19T04:51:08.644Z
close_reason: Landed on claude/diff-core with corpus + oracle + parser tests (50 passing).
---
apply_change_set(manifest, patches, base, resolve_content) -> TreeSnapshot and apply_file_change(change, patch, base_entry, resolve_content) -> TreeEntry. resolve_content is the injected reader so content may be referenced rather than embedded. TreeSnapshot.tree_hash() produces the value the oracle compares against the target tree. Raises NotFullyHydrated when a change lacks what applying it requires — this is what turns the availability states into a checked claim rather than an annotation.
