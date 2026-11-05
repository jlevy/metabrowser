---
type: is
id: is-01m6pt1a1kgdp4myh1scekn2wz
title: Interleave commit summaries in PR Conversation
kind: feature
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-05T21:32:29.618Z
updated_at: 2026-11-05T23:53:01.596Z
started_at: 2026-11-05T21:34:05.272Z
---
Review the plan and implement compact clickable commits in Conversation for managed repositories and existing checkouts. Use verified bounded GitHub metadata and provider ordering, preserve offline behavior, and keep description and speculative fetch budgets unchanged.

## Notes

The Pulls plan now specifies provider-ordered compact commit rows between comments and reviews, cache and source/reader/head validation, canonical GitHub fallback and safe local commit navigation. Public mixed-timeline projection returned 5, 8, and 74 events with no discussion bodies. Five alternating pairs on public PR #283 took 710–882 ms for 50 events and 830–947 ms for 100, where 50 needed a second page and 100 completed. Next implementation step is an integrated selected-PR trial comparing useful description and full Conversation paint, with unchanged visible-row query and no Git object work. Provider ordering and link behavior should have golden and manual coverage in both source modes.

Independent design review added lossless discussion identity, an independently cached projection bound to the discussion revision, and acceptance cases for offline held records, a late page after leaving the PR, and local commit links that never start object acquisition.
