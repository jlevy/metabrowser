---
type: is
id: is-01m76qyz83bat130hty0bkqfam
title: "PR #361 A3: automatic polling can supersede an explicit runtime choice"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76qyxmt9sy6zr9ffwqe0eqs
hold: null
hold_until: null
created_at: 2026-11-12T02:04:06.786Z
updated_at: 2026-11-12T03:38:15.812Z
started_at: 2026-11-12T02:04:20.841Z
closed_at: 2026-11-12T03:38:15.810Z
close_reason: "Fixed in f58eb702: a choice counts as busy (A3); RuntimeRecheckTests."
resolution: null
duplicate_of: null
---
Medium. AppDelegate.swift:447, RuntimeSelection.startChoice. Review A3: https://github.com/jlevy/metabrowser/pull/361
