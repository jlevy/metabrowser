---
type: is
id: is-01m776x4k1tyqj17k9ekwv0be3
title: "Review A3 on #363: gate startup failures leave servers running and the command hanging"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T06:25:15.360Z
updated_at: 2026-11-12T06:58:53.015Z
started_at: 2026-11-12T06:25:21.605Z
closed_at: 2026-11-12T06:58:53.014Z
close_reason: "Fixed in 568cb4fc and fc914e0c (#363): webkit-gate/processes.mjs owns every process from its spawn, metab runs with --exit-on-eof on a held pipe; processes.test.mjs and end-to-end missing-Chrome and startup-timeout runs."
resolution: null
duplicate_of: null
---
Both servers started before the cleanup try/finally, machineFacts() rejects without Chrome, and startMetab() never stopped a server that missed its deadline. Own cleanup from the moment each process or listener starts; start the corpus metab with --exit-on-eof.
