---
type: is
id: is-01kzyp82r1hbkx870at8tgt0xk
title: Align Treemap distribution colors with semantic families
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-13-semantic-file-type-families.md
labels:
  - file-types
  - treemap
  - design-system
dependencies:
  - type: blocks
    target: is-01kzyp89g0kfj93q870sgbaqzk
parent_id: is-01kzyp6zfgt2xkj2wepzx6n5cq
created_at: 2026-08-13T23:10:19.904Z
updated_at: 2026-08-13T23:10:26.815Z
---
Route recognized file and dominant-folder extensions through the shared family distribution key in category_palette.js and the Treemap model/renderer. Keep exact file icons and labels unchanged, keep unknown extensions keyed individually, keep aggregate tails neutral, preserve palette lease disposal, and verify that Overview parents, Overview children, Treemap files, and Treemap folders use the same mounted family color.
