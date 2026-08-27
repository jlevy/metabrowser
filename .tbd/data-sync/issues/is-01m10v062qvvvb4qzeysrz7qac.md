---
type: is
id: is-01m10v062qvvvb4qzeysrz7qac
title: "Salvage and reconcile PR #12 research"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-27T05:27:34.742Z
updated_at: 2026-08-27T15:27:40.315Z
closed_at: 2026-08-27T05:44:28.777Z
close_reason: "PR #87 preserves the current toolchain research and historical spike evidence, reconciles the active docs, passes local and GitHub gates, and supersedes closed PR #12."
resolution: null
duplicate_of: null
---
Extract the durable browser-toolchain research and historical diff benchmark evidence from PR #12, reconcile both with current main, review and validate the documentation, open a replacement PR, and close PR #12 with a disposition map.

## Notes

Extended in PR #87 with a currency review of the full research set. Seven records stay in the active index; the historical diff view spike results moved to docs/project/research/archive/. Reconciled the web diff viewer research with production (diff shipped in core, no renderer library adopted, four open decisions settled), corrected the markdown link navigation summary, fixed two broken plan links in the file patch formats record and registered it in the index, and gave docs/project/README.md a stated keep-vs-archive rule. Pre-existing broken links elsewhere in docs/project/ and the missing make verify link check are tracked separately.
