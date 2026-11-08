---
type: is
id: is-01m6wpacpj9wtx02rt1g8kx49m
title: Design a Files workflow for working trees and cached branch snapshots
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-08T04:22:59.537Z
updated_at: 2026-11-08T04:22:59.537Z
---
Future workflow requested November7, deferred explicitly by the user until current UI work is stabilized and merged. Files should make both a live working tree and read-only cached branch snapshots accessible, with main as the initial branch-browsing choice and a link able to select a specified branch. Existing source-ref-selector is only mounted for managed cached Git revisions with a mirror; filesystem checkout views currently lack it. Research and map the design before significant implementation: source selection semantics, default/fallback branch, preserving live local edits, cache/lender reuse without git checkout or writes to the served repository, link semantics and current one-server-one-pin/same-origin POST boundaries, shared ref-chip chooser styling, state restoration and both source modes. Do not implement or expand the current merge scope for this bead. User's latest instruction is only to track the workflow for future work.
