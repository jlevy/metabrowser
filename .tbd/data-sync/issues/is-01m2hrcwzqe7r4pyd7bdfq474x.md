---
type: is
id: is-01m2hrcwzqe7r4pyd7bdfq474x
title: "Flat mega-tree: walk under an attached browser is 1.6-1.8x v0.9.1"
kind: bug
status: open
priority: 1
version: 1
labels:
  - performance
  - inventory-engine
dependencies: []
created_at: 2026-09-15T05:24:52.854Z
updated_at: 2026-09-15T05:24:52.854Z
---
exp-034 measured five back-to-back pairs on the 300k flat corpus (`build_corpus` shape
2, 300,000 files in 1,104 directories). The walk with a browser attached is 1.62-1.78x
v0.9.1 in every pair on a quiet host. Backend-only `index_done` is 1.13-1.30x over the
same pairs, so attaching a browser roughly doubles the gap: the extra time is driven by
what the browser asks for, not by the walker alone.

The mechanism is the delivery path, measured at about 14 us per entry: a browser
attached during a walk pays for an entry query, a contract entry, a projection, a
decoration and a wire record per discovered entry. On a repository shape that cost buys
content immediately and is worth it; at 300,000 flat entries it dominates and there is
no reader benefit to weigh against it.

exp-035 accepted v0.10.0 by scoping the first-row gate to the corpus class it was
calibrated from, and recorded this regression as knowingly shipped rather than fixed.
`performance-budgets-flat-stress.toml` ratchets the flat shape at its current behavior
so it cannot get worse while this is paid down.

Not a constant to tune. The measured constants are worth about 4% between them (see the
sibling beads); this is structural work on the delivery path.

Done when: the flat-shape walk under an attached browser is at parity with v0.9.1 or
better, measured as five back-to-back pairs on a quiet host, and the flat-stress ratchet
is lowered to the new behavior.
