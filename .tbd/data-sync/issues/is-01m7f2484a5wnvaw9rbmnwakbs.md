---
type: is
id: is-01m7f2484a5wnvaw9rbmnwakbs
title: "PR Conversation: commits that arrive late append after Review comments instead of taking their time order"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T07:35:40.937Z
updated_at: 2026-11-15T07:35:40.937Z
---
Found while building mb-g3ao (the Conversation timeline line, pull request 6 of the 2026-11-15 plan stack).

On a pull request's Conversation tab, commits that are fetched after the Conversation first paints are appended after everything, including the Review comments section. A later repaint puts the same commits among the comment and review cards, in time order. So the same page shows its events in two different orders depending on when the commits arrived. With mb-g3ao's timeline line, a late run of commits also gets a separate line under Review comments rather than joining the cards above.

The event order is data semantics (AGENTS.md parity rules): which events show, in what order. It belongs to the browserless pull page model and its golden, not to the paint.

Done when:
- late commits take the same place in the timeline, in time order among comments and reviews, that a repaint gives them, without moving the reader's scroll position or focus when they arrive;
- the order is pinned in the pull page session's golden for both arrival timings;
- mb-g3ao's Chrome timeline test shows one continuous line in both orders.
