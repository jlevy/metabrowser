---
type: is
id: is-01m748xxadyc5tfdj366df1ag0
title: "App: metabrowser:// scheme, rendezvous handler, and attach"
kind: feature
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:54.540Z
updated_at: 2026-11-11T22:51:49.325Z
---
Phase 3, spike branch. Register the scheme (the URL carries only a rendezvous name or an already-added root); a rendezvous handler that replies with what it did; attach to a live server the app does not own and show its owner; new roots by link need an in-app confirmation.

## Notes

2026-11-11, from review A on jlevy/metabrowser#352 (fixed in 083af6f8): any root without a live server needs an in-app confirmation before the app starts a server, whether it arrives by link or by rendezvous; otherwise the app replies declined. Each trust profile gets its own WKWebsiteDataStore.

2026-11-11, from review B on jlevy/metabrowser#352 (fixed in 5136540f): supersedes the previous note's data-store remark: a WKWebsiteDataStore per trust profile keeps preferences and storage apart but does not bound where credentials go. With the header-token option, the app hands the credential only to frames whose security origin matches, and its navigation policy keeps cross-port navigations out of a view.

2026-11-11, from review C on jlevy/metabrowser#352 (fixed in 3669a358), superseding the earlier credential notes: the app hands the token only to a frame whose WKFrameInfo.securityOrigin matches; a data store per trust profile is for preferences and storage only; no per-server host names or cookies.
