---
type: is
id: is-01m6sx9vy43qz7syctdkmhf455
title: Verify the landed PR support stack and reconcile release documentation
kind: task
status: in_progress
priority: 1
version: 6
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
updated_at: 2026-11-08T03:19:20.541Z
started_at: 2026-11-08T01:50:13.593Z
---
After the owner lands native stack #302, verify the resulting main commit and installed wheel in the managed GitHub and existing checkout modes. Reconcile user guides, design and architecture docs, active specs, shipped skill, and bead dispositions. Compare final acceptance with the exact pre-merge gate and track any release-tag-only validation on mb-8pyc.

## Notes

November 7 release-preparation checkpoint: Post-landing main 68534af93 passed make verify: 4916 tests/9 expected skips (1048.15 s), 385 goldens (195.28 s), audits, distribution and installed-wheel smoke checks. All nine exact-main CI jobs passed. Global aliases and three previews now run exact wheel 0.11.1.dev1272+68534af93 (SHA256 9b5ebaad3c6271acbc15795a7651c1fc4524777f24e1d2ce0213025cd92100c7), ten byte-matching assets per port, skill content current/source pin advanced. Built-in-browser managed and checkout PR327 sessions pass Conversation/Changes/Checks, stack titles/menu/ShiftK preserving Checks, #title/#number Quick Search, Files/Pulls independent routes, document/source gutters and neutral commit prose. Managed preview switched through UI to actual main. Source macOS20 and live-GitHub8 pass separately. Runtime acceptance is complete; documentation reconciliation is staged on codex/v012-release-preparation-20261107 and must be reviewed/published/landed before this bead closes. Release comparisons and owner approval remain separate.

The user now explicitly authorizes the agent to merge the reviewed, green stack, then prepare the release. After native stack302 lands, verify exact main/CI/tree parity, run the required full release gate, reconcile current docs/plans/skill/beads, install the verified main wheel, and prepare release notes and evidence. Do not create a release tag or publish without approval.
