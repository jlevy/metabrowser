---
type: is
id: is-01m6wkyj7h8z2qxz5amsvrfd1w
title: Place stack positions beside list PR numbers and simplify stack-menu rows
kind: feature
status: closed
priority: 1
version: 5
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
created_at: 2026-11-08T03:41:34.832Z
updated_at: 2026-11-08T05:15:33.720Z
started_at: 2026-11-08T03:41:47.870Z
closed_at: 2026-11-08T05:15:33.720Z
close_reason: Merged through native stack331 (#328–#330) at d33550455d1a44bb275d5e71492f9bdbc682f0c5. The landed tree exactly equals reviewed/gated519c33239. Independent senior review is complete for each layer; UI also has dedicated security/performance passes. All nine checks passed on every exact PR head; full local make verify passed4917 tests/9 expected skips and385 goldens, audits/types/distribution. The exact gated wheel is installed under both aliases, all11 plugins and30 served assets verified, with both repository-mode PR tabs, positional menus, narrow fit, typography and Reload keyboard acceptance. Corpus linked-root regression also passes; separate release gates and final documentation wording remain open.
resolution: null
duplicate_of: null
---
User acceptance on November 7: show the stack icon and position such as6/6 on the left Pulls overview/list beside the PR number. Reuse cached optional native stack metadata and existing navigation/menu behavior; avoid per-row provider fetches. The popover row must read bold position, tiny middle dot, title, tiny middle dot, PR number: **1/6** · title · #123. Keep the position bold and place the PR number to the right of its title, preserving current item, keyboard and native-link behavior. Update the plan/design docs, focused session/golden evidence, review and install through a follow-up PR. Also place the PR-page stack trigger immediately to the right of its Open/Merged/Closed status badge. Keep the disclosure mounted across passive header updates, and keep its menu within narrow panes.
