---
type: is
id: is-01m7v8prb166f74m9855fmntda
title: "macOS Open URL (Cmd-L) of a PR or any in-repo GitHub URL opens a mirror keyed to the item, not the repository: open or reuse one mirror per repo and navigate to the item"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m7v8bs62dz0nqmqb9rnhgsdb
created_at: 2026-11-20T01:21:32.000Z
updated_at: 2026-11-20T01:21:32.000Z
---
Owner, 2026-11-19 in chat: "when I open something like https://github.com/finterm-ai/trading/pull/1178 using cmd-L and paste it in, it does correctly open the trading repo. However, it should open the root of the trading repo, not treat it like an open repo specifically for the PR. If I opened a few PRs, they would all be in the same repo, and it should just switch to the appropriate PR. That's the same for anything else local to a repo. We should just open a repo in cloud mode if it is not already, or if it is cloud mirror mode already and opened we reuse that, sync and navigate to the relevant item."

Expected: one mirror window (one server, keyed by the repository's address: SessionRoot) per repository. Opening any URL inside that repository (a pull request, blob, tree, commit, or branch) reuses the window and its server, starts a refresh, and navigates to the item (/pull/<n>, the file, the commit). If no mirror window exists, open the repository's mirror and land on the item. arch-open-modes.md, The File Menu, already says "If the mirror already has a window, the window switches to the branch or pull request the URL selects". Find where the app or `metab` keys the open on the item's URL instead of the repository's (SessionRoot, LinkSelection, OpenURLPanel, PresentPlan, `metab --present`), and fix it in the app and `metab` together (AGENTS.md: the app's flags and routes are internal).
