---
type: is
id: is-01m6f3add4akft3c0x2p54f5v2
title: Overlay of the served checkout, acquired when Files changed opens
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3adv181gkevbha1epsyj1
parent_id: is-01m6f3a2f5v5bkym87p85a0wq2
created_at: 2026-11-02T21:40:49.699Z
updated_at: 2026-11-03T06:35:26.109Z
---
Step 6, as decided 2026-11-02 by plan-2026-11-02-pr-review-mirror-and-checkout.md (Fit with the Pulls Tab Plan; Finding the Checkout, the Served row; its Delivery step 4). Opening a pull request's Files changed on a folder server creates, the first time, an overlay store borrowing the served checkout's objects, through the acquisition --checkout uses, inside the running server; the comparison is served from that store. Nothing is written to the checkout and no Git runs with it as its repository.
