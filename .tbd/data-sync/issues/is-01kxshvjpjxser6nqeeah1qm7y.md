---
type: is
id: is-01kxshvjpjxser6nqeeah1qm7y
title: "Spike: diff backend manifest+lazy patches and four renderer approaches"
kind: task
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-18-git-diff-view.md
labels:
  - diff
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-07-18T02:46:00.145Z
updated_at: 2026-07-18T03:17:35.092Z
closed_at: 2026-07-18T03:17:35.090Z
close_reason: "Spike complete: manifest-first adapter validated (status ~10ms, numstat 98ms of 109ms manifest, per-file patches 2-3ms); custom gated renderer meets budgets (10-70ms typical, 195ms gated pathological vs 2s full); pierre viable only virtualized+worker+language-subset (default full mount 76s, 10.6MB bundle, esbuild rebuild byte-deterministic); gdv needs git hunks input, DOM slower than custom; server-HTML no advantage. Findings in spikes/diff-view/REPORT.md, plan spec updated."
---
Validate plan-2026-07-18-git-diff-view.md decisions hands-on: hardened git subprocess adapter (porcelain v2, numstat, per-file semantic patches, untracked synthesis) with timings; custom buildless-ESM renderer; @pierre/diffs stable vendored via esbuild; @git-diff-view/core data layer; server-rendered HTML projection. Shared fixtures + Playwright benchmarks. Spike code under spikes/diff-view/, quarantined npm deps, findings in REPORT.md and folded into the plan spec.
