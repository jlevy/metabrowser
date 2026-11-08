---
type: is
id: is-01m6sx9vy43qz7syctdkmhf455
title: Verify the landed PR support stack and reconcile release documentation
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6wdjwawp9g1bvnefz2hxze3
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
child_order_hints:
  - is-01m6wdjwawp9g1bvnefz2hxze3
hold: null
hold_until: null
created_at: 2026-11-07T02:27:19.107Z
updated_at: 2026-11-08T01:58:27.667Z
started_at: 2026-11-08T01:50:13.593Z
---
After the owner lands native stack #302, verify the resulting main commit and installed wheel in the managed GitHub and existing checkout modes. Reconcile user guides, design and architecture docs, active specs, shipped skill, and bead dispositions. Compare final acceptance with the exact pre-merge gate and track any release-tag-only validation on mb-8pyc.

## Notes

The user now explicitly authorizes the agent to merge the reviewed, green stack, then prepare the release. After native stack302 lands, verify exact main/CI/tree parity, run the required full release gate, reconcile current docs/plans/skill/beads, install the verified main wheel, and prepare release notes and evidence. Do not create a release tag or publish without approval.
