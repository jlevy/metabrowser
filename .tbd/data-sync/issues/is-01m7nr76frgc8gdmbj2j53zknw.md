---
type: is
id: is-01m7nr76frgc8gdmbj2j53zknw
title: "Pull request page: Browse code and comment file links become the switch on metabrowser:pin-changed"
kind: task
status: open
priority: 3
version: 1
labels:
  - pulls
  - ui
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-17T21:57:12.823Z
updated_at: 2026-11-17T21:57:12.823Z
---
Follow-up from review A of jlevy/metabrowser#511 (View on branch), finding A6, deferred there as outside the plan's stated scope.

On a pull request's page, Browse code in its link form (`builtin_plugins/github/pull-page.js`, `browseControl`) and a review comment's file link (the `/view/` link the page draws beside a comment) open a `/view/` address, which names no revision. When another tab switches the server's pin, those links open the same path at the other pin. Nothing in `pull-page.js` listens for `metabrowser:pin-changed` (static/source-pin-guard.js), while the diff's View on branch links already turn into the switch back on that event (`onPinChanged` in builtin_plugins/diff/index.js, `repaintViewFileControls` in diff-view.js).

Both controls now share the diff plugin's `createPinSwitch` through `switchPin`, so on `metabrowser:pin-changed` they could become the switch, as the diff's controls do. Add it to the pull-page session with a step that plays the event, beside the diff-view-file session's.
