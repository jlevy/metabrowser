---
type: is
id: is-01m0hj5b44s8vt9sap50651tzr
title: Extract the nav filter decision into a pure, headless-testable module
kind: task
status: closed
priority: 2
version: 3
assignee: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-08-21T07:04:30.083Z
updated_at: 2026-08-21T15:42:19.804Z
closed_at: 2026-08-21T15:42:19.803Z
close_reason: New static/tree_filter_model.js holds the two decisions that needed no DOM — a filter selection as request parameters, and cluster verdicts given row descriptors — with headless coverage in tests/dom/tree_filter_model_behavior.js. app.js keeps only the DOM reads and class writes.
---
`applyTreeFilters` mixes three jobs in one DOM walk: deciding whether a row matches, deciding whether a folder survives on the strength of its descendants, and writing classes onto elements. Only the third needs a DOM, and the first two are what the bugs are in.

Split the decision out into a pure module beside static/filter_state.js and static/tree_expansion.js, taking a tree model and a filter snapshot and returning verdicts and rolled-up totals. app.js keeps the part that applies verdicts to elements.

That gives the same headless Node coverage tests/dom/tree_expansion_behavior.js gets today: fixture tree in, decisions out, no browser and no DOM stub. Add tests/dom/ coverage for the cases the bugs came from — a folder whose only match is past the page cap, a folder whose whole subtree is filtered out, and the selected row.

Note for whoever picks this up: no jsdom in this repo, and adding one is a supply-chain decision (see SUPPLY-CHAIN-SECURITY.md). The existing tests/dom suites hand-roll the small amount of DOM they need, which is the pattern to follow.
