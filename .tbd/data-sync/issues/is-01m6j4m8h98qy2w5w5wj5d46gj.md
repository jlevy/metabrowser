---
type: is
id: is-01m6j4m8h98qy2w5w5wj5d46gj
title: Unify Git status colors, branch chips, and code typography
kind: feature
status: in_progress
priority: 1
version: 7
spec_path: docs/design-system.md
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
child_order_hints:
  - is-01m6j4nf5gxfd2c5kz2c3w6jp6
  - is-01m6j4nfv2b0d7kez853xgwfys
  - is-01m6j4s3nwme980b28j6n0k2gw
  - is-01m6j4s4cat6njdpvbjf1dp8zf
  - is-01m6j5ce0pgcr3zhv1w349e6bk
created_at: 2026-11-04T02:01:24.263Z
updated_at: 2026-11-04T02:14:36.294Z
---
Owner requests a consistent subdued design system across all Git/PR file status letters, branch references and monospace content. Added green, deleted red, modified dark yellow; use shared semantic theme tokens and retain status letters/tooltips. Branch names in Git history, PR history/header/list and other views should use shared dark blue/purple chips. Audit actual code font inheritance and rem/em drift before correcting shared scale and matching virtualized geometry. Implement as a fifth forward-only stacked design-system layer above selection successor224e32aa; preserve current gate source while read-only audits run. Focused contrasts/computed-style/geometry checks and installed-browser review; no new fonts/dependencies/framework. Track three child scopes and independently review before final whole-stack publication.
