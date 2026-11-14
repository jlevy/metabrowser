---
type: is
id: is-01m0k5xff9wt2byqj2ja6yxmq3
title: Move /api/catalog to the on-demand tier, fetched when the finder first opens
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T22:08:58.345Z
updated_at: 2026-11-14T18:42:18.495Z
---
Defer the first /api/catalog fetch on a directory page until Quick Search first opens, taking the bulk catalog off the load path.

The buffering policy this needs exists. catalog-feed.js hold() and release() (commit b8d03f0e) journal nothing while held and start one authoritative fetch on release, and app.js holds the feed on a pull-request page until its palette or a file releases it. What remains is holding it on a directory page, releasing it when the palette opens, and measuring the trade: bytes and main-thread time off the load path against a first palette open that waits for the catalog.

H4 could not price this on build_corpus, whose catalog was 62 bytes. exp-034 measured a 15.9 MB /api/catalog body at 300,000 rows on the flat shape-2 corpus (mb-qtgj), so that corpus can. The feed starts today from the EventSource onopen handler in _createInventoryEventSource (app.js) and from startInventoryEventStream's no-EventSource path.
