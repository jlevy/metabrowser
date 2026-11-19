---
type: is
id: is-01m748xwf9kpmst8t6jk2n95hj
title: Page follows navigate events and reloads once on a new boot id
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:53.672Z
updated_at: 2026-11-19T16:49:34.080Z
---
Phase 3. The page navigates on a navigate event, reloads once when the boot id changes, and refuses a root mismatch instead of silently reattaching. A browserless golden session against the production JavaScript.

## Notes

2026-11-11, from review C on jlevy/metabrowser#352 (fixed in 3669a358), superseding the earlier credential notes: the event stream may move from EventSource to a streamed fetch carrying the Authorization header; depends on mb-qzny's event-stream gate.

2026-11-19: restructured under host mode plan HM-1 A (docs/project/specs/active/plan-2026-11-18-host-mode.md, step H6). It now waits on mb-hhzd (H1), which gives the boot ID, in place of mb-1zyp. Its follow half is the view model's V4 applier, the ui.intent event on the viewer's stream, rather than a navigate from mb-1zyp. The event stream's move to a streamed fetch comes with the token, mb-qzny (H8), after this bead.
