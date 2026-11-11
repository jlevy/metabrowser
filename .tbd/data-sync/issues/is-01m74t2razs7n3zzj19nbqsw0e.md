---
type: is
id: is-01m74t2razs7n3zzj19nbqsw0e
title: "PR #346 A10: cite or mark Planned the trusted-profile overlay test in the mirror-and-checkout plan"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m74t21pvwps4wh189z73rspr
created_at: 2026-11-11T08:02:39.070Z
updated_at: 2026-11-11T08:21:22.138Z
closed_at: 2026-11-11T08:21:22.137Z
close_reason: "Fixed in 6c1bc550 (mark Planned): the plan bullet now says the every-entry-point trusted-profile test is Planned (Parity and Tests trust row) and that tests/test_checkout_overlay.py checks only that borrowing cannot change the untrusted profile."
resolution: null
duplicate_of: null
---
Suggestion. plan-2026-11-02-pr-review-mirror-and-checkout.md (about lines 604-611) turned a claim that a test asserts no PR blob is served under the trusted profile over every route into an instruction; no such test found (tests/test_checkout_overlay.py:1265-1330 covers the untrusted profile). Cite the test or mark Planned. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5855482052 (PR #346, review A, round 1).
