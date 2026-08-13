---
type: is
id: is-01kzyp7vt7qe3e25d01w11db8g
title: Render collapsible semantic families in the folder Files summary
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-13-semantic-file-type-families.md
labels:
  - file-types
  - folder-overview
  - accessibility
dependencies:
  - type: blocks
    target: is-01kzyp82r1hbkx870at8tgt0xk
  - type: blocks
    target: is-01kzyp89g0kfj93q870sgbaqzk
parent_id: is-01kzyp6zfgt2xkj2wepzx6n5cq
created_at: 2026-08-13T23:10:12.806Z
updated_at: 2026-08-13T23:10:26.815Z
---
Update the folder summary model, renderer, and styles to place family parents and raw fallbacks inside Documentation, Code, Data, and Other. Family parents are text-only aggregate rows with folder-relative metrics and a trailing accessible chevron only when two or more canonical children are present. Children start hidden, use exact extension icons, preserve family expansion and focus across live updates, share the parent palette key, and retain responsive, reduced-motion, print, and terminal-state behavior.
