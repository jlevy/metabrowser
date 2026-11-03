---
type: is
id: is-01m6f3a2f5v5bkym87p85a0wq2
title: "Step 6: Files changed on a checkout, from an overlay of the served checkout"
kind: feature
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6f3add4akft3c0x2p54f5v2
  - is-01m6f3adv181gkevbha1epsyj1
created_at: 2026-11-02T21:40:38.500Z
updated_at: 2026-11-03T06:47:10.100Z
---
Delivery step 6. When the base and head commits are in the checkout, the page shows the diff with read-only Git and names the base it used. When they are missing, it says so, writes nothing, and gives the two commands.

## Notes

2026-11-03 status: the plan's step 6 is revised (483b3a17): Files changed on a checkout reads an overlay store borrowing the served checkout's objects, created when the reader opens Files changed, per plan-2026-11-02-pr-review-mirror-and-checkout.md. Not started; it follows step 5. Children mb-5bqy and mb-awvw are rewritten to match.

2026-11-02: gate updated, reported by the other session: the owner accepted the overlay store design, taking every recommendation. Plan: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md on claude/v012-pr-review-design at b330e0c9; read its Fit with the Pulls Tab Plan and Finding the Checkout sections before designing this step. It assumes: no-loss is relaxed for overlays; only a checkout named with --checkout or served with metab <checkout> may lend, so a metab <checkout> server opening a pull request is a legitimate lender with zero flags; an uncertain merge base deepens as a bounded job and reads base_uncertain meanwhile and offline; an existing full mirror is kept and the conversion printed; borrows sits beside location in status and the heading tooltip. Do not start until the other session says its overlay step 1 on claude/v012-overlay-acquisition is reviewed. That plan's step 4 rewrites the Pulls plan's step 5 text.

2026-11-02: GATE. Same as mb-cbak: wait for the owner's decision on the overlay store proposal before fixing this step's design.
