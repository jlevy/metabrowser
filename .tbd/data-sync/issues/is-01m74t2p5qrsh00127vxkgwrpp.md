---
type: is
id: is-01m74t2p5qrsh00127vxkgwrpp
title: "PR #346 A5: docs no longer state that a borrowing refusal never falls back to a full clone"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74t21pvwps4wh189z73rspr
created_at: 2026-11-11T08:02:36.855Z
updated_at: 2026-11-11T08:21:20.738Z
closed_at: 2026-11-11T08:21:20.737Z
close_reason: "Fixed in 6c1bc550: the no-full-clone sentence is back in docs/command-line.md, docs/reviewing-pull-requests.md, and the mirror-and-checkout plan step 5. Docs only; make lint-check (flowmark) passed."
resolution: null
duplicate_of: null
---
Low. docs/command-line.md:385-390, docs/reviewing-pull-requests.md:283-286, plan-2026-11-02-pr-review-mirror-and-checkout.md step 5 lost the no-full-clone guarantee (code: checkout.py:333 allow_clone_fallback=False). Fix: restore one sentence. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5855482052 (PR #346, review A, round 1).
