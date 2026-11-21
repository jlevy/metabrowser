---
type: is
id: is-01m7wyrvxk2xx44pqtqmy5cq5g
title: "Source and checkout kinds: one mode and one icon for a cloud mirror, a Git checkout, and a plain folder"
kind: epic
status: in_progress
priority: 1
version: 12
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/667
    at: 2026-11-20T19:14:58.719Z
labels:
  - linear
  - Improvement
dependencies: []
child_order_hints:
  - is-01m7wxbwfxt3m6b3nbs2wy4v44
  - is-01m7p8hjk6jd7ckmr0fnjmpqca
  - is-01m7pn8n0nyp1y7mj41d1b38wm
  - is-01m7pn8nk5a2cfd92t8fen4gv4
  - is-01m7zt8s6hyeah3vfpm02rb6zf
  - is-01m7zt8tjfje20937mytx38qr8
created_at: 2026-11-20T17:06:24.306Z
updated_at: 2026-11-21T19:45:27.630Z
extensions:
  linear:
    id: 74de802a-b5dd-4672-8169-c0ba864abbc5
    linked_at: 2026-11-20T19:16:44.113Z
---
What a reader has open is one of three kinds: a cloud mirror of a GitHub repository, a local folder inside a Git checkout (folder mode), or a plain folder with no Git. The model is settled in docs/project/architecture/arch-open-modes.md (#558), and the macOS app's title bar, Open Recent and Dock menus already carry the shared marks (#564, #575).

What remains: the kind icon and tooltip beside the root name at the top of the nav, and a Source kind section with a check in the design system's icon catalog (mb-4s2y, in progress); the shared local-open resolver (mb-2wfk) with its vocabulary test and shared fixture (mb-ajxe); and the owner's request that every view say plainly which mode it is in (mb-wup3), whose indicator mb-4s2y overlaps. How a branch behaves in each kind is the epic mb-2uut.
