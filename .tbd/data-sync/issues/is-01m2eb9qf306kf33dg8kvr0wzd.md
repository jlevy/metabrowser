---
type: is
id: is-01m2eb9qf306kf33dg8kvr0wzd
title: "Markdown: deferred review findings (transclusion deadline, task-box pairing, truncated catalog, worker reuse, real-browser coverage)"
kind: bug
status: open
priority: 2
version: 2
labels:
  - markdown
dependencies: []
created_at: 2026-09-13T21:38:14.114Z
updated_at: 2026-09-14T03:19:58.272Z
---
From the release senior review (Markdown lane). Verified issues deferred from the v0.9.2 release because they are present on main or need measurement rather than a local fix:

- Shared transclusion deadline (transclusion.js, wiki-enhancer.js): the 5 s wall clock starts at the first embed that resolves, so an embed whose catalog resolves 6 s later is permanently timed-out. Time out per claim. Present on main.
- Stray `[` pairing (wiki-parser.js ~666-683): `- [ ] Review [[Meeting Notes]] per [spec](https://x)` is not converted because the task box's `[` matches the later `](`. Present on main.
- A walk truncated at INVENTORY_MAX_FILES never calls markComplete(), so fallback wiki links and rooted extensionless links say "Resolving..." forever and the reconciliation coordinator re-runs all jobs on every live change. Treat a truncated terminal state as final and report catalog-truncated.
- Each Markdown mount (every navigation and folder README panel) constructs and terminates a module Worker; share one lazily created client if the Worker stays.
- MAX_ELEMENTS_PER_CALLBACK, the 4,096 enhancement cap, and the 5,000 ms transclusion budget carry no recorded measurement (AGENTS.md: measure before bounding).
- The Worker, TreeWalker, and scroll paths never run in a real browser under make verify, which is how the in-document navigation regression shipped to review; add a small headless-Chromium session for link admission and fragment scrolling.

## Notes

PR #114 (claude/markdown-deferred-fixes) fixes the transclusion deadline (per-embed allowance), task-box bracket pairing, truncated-catalog final state (`catalog-truncated` outcome, `fileCatalog.snapshot().truncated`), and shares one Markdown preprocessing Worker across mounts.

Still open here:
- Record measurements for MAX_ELEMENTS_PER_CALLBACK, the 4,096 enhancement cap, and the 5,000 ms transclusion budget.
- Real-browser (headless Chromium) coverage for the Worker, TreeWalker, link admission, and fragment-scrolling paths.
