---
type: is
id: is-01m2eb9qf306kf33dg8kvr0wzd
title: "Markdown: measure the enhancement and transclusion bounds, and add real-browser coverage"
kind: bug
status: open
priority: 2
version: 8
labels:
  - markdown
dependencies:
  - type: blocks
    target: is-01m2f38npt37vtbyys1t8bgp7s
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
child_order_hints:
  - is-01m2f0fb55v9h6480r6cfx514k
created_at: 2026-09-13T21:38:14.114Z
updated_at: 2026-11-20T17:13:32.020Z
---
Remaining from the v0.9.2 release review (Markdown lane). PR #114 fixed the shared transclusion deadline, task-box bracket pairing, the truncated-catalog final state and per-mount Worker construction.

- Record a measurement beside each bound that has none (AGENTS.md: measure before bounding): MAX_ELEMENTS_PER_CALLBACK = 32 and MAX_RECONCILIATION_JOBS = 4096 (reconciliation-coordinator.js), MAX_ENHANCED_TARGETS = 4096 (dom-traversal.js), MAX_WIKI_ELEMENTS = 4096 (wiki-enhancer.js), and the 5,000 ms per-embed transclusion budget (transclusion.js DEFAULT_MAX_TRANSCLUSION_DURATION_MS).
- Add a headless-Chromium session for the Markdown Worker, TreeWalker, link admission and fragment scrolling, which no Chrome test under tests/dom covers today. Use it to measure staged-navigation latency with the primary-first Worker lane, and as the harness mb-k0s0 needs.

## Notes

PR #114 (claude/markdown-deferred-fixes) fixes the transclusion deadline (per-embed allowance), task-box bracket pairing, truncated-catalog final state (`catalog-truncated` outcome, `fileCatalog.snapshot().truncated`), and shares one Markdown preprocessing Worker across mounts.

Still open here:
- Record measurements for MAX_ELEMENTS_PER_CALLBACK, the 4,096 enhancement cap, and the 5,000 ms transclusion budget.
- Real-browser (headless Chromium) coverage for the Worker, TreeWalker, link admission, and fragment-scrolling paths.

PR #114 review (https://github.com/jlevy/metabrowser/pull/114#pullrequestreview-5193705916) addressed in de282ce5, tracked as mb-jynh: primary-first Worker lane (R1), page-wide fatal failure documented (R2), nested-link-label parser fixes (R3), truncated -> complete re-resolution (R4), capped-walk search status (R5), plus suggestions.
- The real-browser work above should also measure staged-navigation latency with the primary-first Worker lane (not measured in PR #114).
- Follow-ups: mb-fvs1 (optimistic navigation for explicit-path wiki misses on a truncated catalog), mb-k0s0 (latch the shared Worker after a deterministic load failure; needs the real-browser harness).

2026-11-14 audit: title and description narrowed to the two items still open after PR #114. Standalone (label markdown): no open epic owns Markdown engine robustness; mb-fbm2 covers future extensions only.
