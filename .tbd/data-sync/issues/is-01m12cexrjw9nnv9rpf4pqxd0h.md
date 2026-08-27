---
type: is
id: is-01m12cexrjw9nnv9rpf4pqxd0h
title: Document Git and comparison-source architecture
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-27T19:51:57.957Z
updated_at: 2026-08-27T19:59:16.099Z
closed_at: 2026-08-27T19:59:16.097Z
close_reason: Created docs/project/architecture/arch-git-and-comparison-sources.md in 12f1cd0, with tests/test_git_arch_doc.py enforcing the route table, named modules, and the single-subprocess-path invariant. Linked from the project index, the views/models/routes map, and diff-sources-and-anchoring. GitHub deferred to its own doc when provider code lands.
resolution: null
duplicate_of: null
---
Create docs/project/architecture/arch-git-and-comparison-sources.md: the three-layer stack (File Diff Format -> Git -> providers), the subprocess boundary invariants, byte discipline, discovery and root gate, the /api/git collection API with an enforced route table, the modeling idiom (Pydantic vs TypedDict) and its intended direction, the DiffSource port and the rule for adding a comparison source, and the provider boundary. GitHub gets its own doc when Phase 4 lands code. Found while auditing docs after the PR #31 review: the diff side is documented, the Git side lives only in plan specs.
