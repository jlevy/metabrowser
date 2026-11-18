---
type: is
id: is-01m7pvpehjbses9hzggv3ahw4d
title: "App: switch an open repository window to a link's revision in place, without a server restart"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7nyeb57h28trbdp2m1hy2wk
created_at: 2026-11-18T08:17:12.753Z
updated_at: 2026-11-18T08:17:12.753Z
---
From PR #539's addressing: owner decision 1 is met for now by restarting the repository's server on the link (never shows another revision, but costs a few seconds, a new port and fresh local storage, and restarts even for the same revision). Switch in place instead: a pin switch that takes a link, or a ref field in --present's dry run (only the mirror knows where a slash-holding ref ends).
