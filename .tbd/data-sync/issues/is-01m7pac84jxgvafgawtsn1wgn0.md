---
type: is
id: is-01m7pac84jxgvafgawtsn1wgn0
title: "View header: a small, clear toggle in the upper right between a gray Metabrowser icon (this view) and the GitHub icon (the same item's page on github.com)"
kind: task
status: closed
priority: 2
version: 6
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
child_order_hints:
  - is-01m7pdvnf87n53mhhjyrjqj9dw
hold: null
hold_until: null
created_at: 2026-11-18T03:14:32.720Z
updated_at: 2026-11-18T22:04:06.578Z
started_at: 2026-11-18T03:15:32.467Z
closed_at: 2026-11-18T22:04:06.577Z
close_reason: Landed in jlevy/metabrowser#552 (8b8ef2ec7); the app's in-window GitHub view stays mb-lxgw
resolution: null
duplicate_of: null
---
Owner, 2026-11-18 in chat: 'then we want the upper right to be a toggle between a gray version of the metabrowser icon and the github icon. it should be small but clear.' Asked what it does, the owner chose: switch between Metabrowser's view and the item's page on github.com (like an always-visible View on GitHub). Lands with mb-6x33 in one PR. Shown only where a GitHub page exists for the item; hidden otherwise.

## Notes

2026-11-18 owner (chat): 'It's distinct from the open mode. It is a persistent toggle that lets you see the corresponding GitHub page if appropriate. This would only appear on pages that have a corresponding GitHub repo, for pure use as a local folder without a GitHub repo that's the plain folder mode and it wouldn't have those choices.' Separate from mb-wup3's mode indicator; two-state switch whose choice persists; absent on a plain local folder.
2026-11-18 owner (chat): 'In general, pages should open in the Metabrowser view, but you should always be able to switch to the GitHub view, and then it's simply a web view onto that page on github.com.' Default Metabrowser view on every open; GitHub state = a web view of github.com (in the macOS app, inside the window with the toggle kept reachable; in a browser github.com refuses framing, so it opens the page as View on GitHub does).
