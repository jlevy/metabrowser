---
type: is
id: is-01m6gab1sz6qn15qwkpe0wtnha
title: "Recorders: close owned pin readers on the serving event loop"
kind: bug
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6g771qn4n0pce8m7sdmmhxy
hold: null
hold_until: null
created_at: 2026-11-03T09:02:45.054Z
updated_at: 2026-11-03T09:05:03.020Z
started_at: 2026-11-03T09:05:02.695Z
---
The page recorder manually attached a closed subject with no opener. Pin switches then created owned live subjects which the no-opener lifespan did not close. Under failed-only pytest temp retention, the subsequent panel recorder could reuse the same truncated cache directory and inherit a batch reader tied to a closed event loop. Use serve_subject_opener in both recorders so startup and shutdown own the readers. Production pool behavior is unchanged; the page and panel recorder modules pass together after the fix.

## Notes

Fixed locally in cc4e9127; recheck pin be99626f. Both recorders use serve_subject_opener so the application serving loop owns startup, pin replacement, and shutdown. The previously failing page/panel combination passes seven tests, and the focused selection excluding the CLI module with the known remote gh-log ordering fix passes 181 tests under failed-only temp retention. No production reader-pool change. Awaiting independent recheck and coordinator push.
