---
type: is
id: is-01m6wkzscv76q4b3w6resytamt
title: Use a leading GitHub brand icon for View on GitHub
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m6wdjwawp9g1bvnefz2hxze3
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-08T03:42:14.938Z
updated_at: 2026-11-08T05:15:33.726Z
started_at: 2026-11-08T03:48:07.924Z
closed_at: 2026-11-08T05:15:33.726Z
close_reason: Merged through native stack331 (#328–#330) at d33550455d1a44bb275d5e71492f9bdbc682f0c5. The landed tree exactly equals reviewed/gated519c33239. Independent senior review is complete for each layer; UI also has dedicated security/performance passes. All nine checks passed on every exact PR head; full local make verify passed4917 tests/9 expected skips and385 goldens, audits/types/distribution. The exact gated wheel is installed under both aliases, all11 plugins and30 served assets verified, with both repository-mode PR tabs, positional menus, narrow fit, typography and Reload keyboard acceptance. Corpus linked-root regression also passes; separate release gates and final documentation wording remain open.
resolution: null
duplicate_of: null
---
User acceptance on November7: the PR-page View on GitHub link must use the actual GitHub brand icon before its text, rather than a trailing PR-state icon. Reuse the shared external-link/icon primitive where possible, keep external-link safety attributes and accessible naming, and verify the actual browser output and focused production behavior. Track with the new Pulls typography/stack acceptance follow-up and install the final reviewed build.
