---
type: is
id: is-01m7hdmp7nrsd3y6tgjgmfks5k
title: "PR #458 A5: fixed sleep(400) waits for the drawer transition in the Files session"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjeyyagvt3h7zcvvssfks
hold: null
hold_until: null
created_at: 2026-11-16T05:35:22.868Z
updated_at: 2026-11-16T06:16:21.750Z
started_at: 2026-11-16T05:35:30.126Z
closed_at: 2026-11-16T06:16:21.749Z
close_reason: "Fixed in 3ed205983 on PR #458; disposition reply https://github.com/jlevy/metabrowser/pull/458#issuecomment-6908956491"
resolution: null
duplicate_of: null
---
Low (suggestion). Review A https://github.com/jlevy/metabrowser/pull/458#pullrequestreview-5915435915. tests/dom/files-tab-chrome.mjs:456, :463, :487. Synchronize on observable state (the bar's transitions finishing) instead of fixed sleeps, with one helper at all three sites.
