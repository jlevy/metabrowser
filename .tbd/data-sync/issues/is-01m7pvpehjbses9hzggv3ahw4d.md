---
type: is
id: is-01m7pvpehjbses9hzggv3ahw4d
title: "App: switch an open repository window to a link's revision in place, without a server restart"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7nyeb57h28trbdp2m1hy2wk
created_at: 2026-11-18T08:17:12.753Z
updated_at: 2026-11-18T16:22:55.971Z
---
From PR #539's addressing: owner decision 1 is met for now by restarting the repository's server on the link (never shows another revision, but costs a few seconds, a new port and fresh local storage, and restarts even for the same revision). Switch in place instead: a pin switch that takes a link, or a ref field in --present's dry run (only the mirror knows where a slash-holding ref ends).

## Notes

2026-11-18, review C1 on PR #539: a restart on a link whose branch, tag, or commit the mirror lacks serves the default branch at /view/ while metab fetches it (git_pin_cli.py); /api/source/status says selection_state pending, then found (the page goes to selection_href itself) or not_found / fetch_failed (the windows stay on the default branch). PR #539 now says so in the guide and arch-macos-app.md, and the app watches /api/source/status after each repository start (LinkSelection) and raises an alert for not_found and fetch_failed. Still open here: keeping the windows on the starting view while the selection is pending, then loading selection_href, so no window shows another revision even briefly; an in-place switch that takes a link would close it.
