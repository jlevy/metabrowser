---
type: is
id: is-01m74t2pkmbpcgfrxc69mcw00j
title: "PR #346 A6: contract text still describes explicit-only acquisition"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74t21pvwps4wh189z73rspr
created_at: 2026-11-11T08:02:37.299Z
updated_at: 2026-11-11T08:21:21.073Z
closed_at: 2026-11-11T08:21:21.072Z
close_reason: "Fixed in 6c1bc550: arch-views-models-routes.md, pull_route.py RefreshRequest and _start_refresh, sidekick.py pull_refresh_handler, the pulls-tab plan contract and step 6 now name the Changes page's one comparison request; the checkout golden narration says 'A comparison request attaches the cached store without changing the folder'. Confirmed by tests/test_cli_github_checkout_golden.py (passed)."
resolution: null
duplicate_of: null
---
Low. arch-views-models-routes.md:284-286, pull_route.py:481 and :571, sidekick.py:341, plan-2026-10-01-github-pulls-tab.md:682 and :1440-1442, tests/test_cli_github_checkout_golden.py:246 and tests/golden/cli-github-checkout.txt:1205 still say retry:true is only a reader's press or name an explicit Fetch. Fix: reword and update the golden narration. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5855482052 (PR #346, review A, round 1).
