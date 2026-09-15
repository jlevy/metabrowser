---
type: is
id: is-01m10vgwqwn8gjdv8fm183vztr
title: "Hosted review Phase 4: PR documents, diffs, and virtual nav collection"
kind: feature
status: open
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m0b71xgqp0jgz007h0wtzr3z
  - type: blocks
    target: is-01m10xd6s2fy7qthahs3cz25gk
  - type: blocks
    target: is-01m2h5ar8jct8wbp94xj39gkq4
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m0b71xwkrf39qnq9ccgxmfp4
  - is-01kxry31tw40txkbzctzv1mtsd
created_at: 2026-08-27T05:36:42.234Z
updated_at: 2026-09-14T23:59:18.730Z
---
Render provider-neutral hosted-review records through plugin-owned views. Add a Pull Requests nav panel backed by ChangeRequestIndex with Git-history-style bounded paging, virtualization, focus, selection, and restoration; model its root as a virtual folder-like collection and each PR as an item-like frontmatter document plus a folder-like container of changed files. Compose validated metadata, Markdown description, reviews, threads, checks, merge/freshness/offline states, File Diff Format, and revision content without provider branches in common views. Direct GitHub PR URLs open the same record identity. Counts and visibility come from the complete bounded model, not mounted rows. Issues remain mb-9rrc.
