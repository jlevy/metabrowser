---
type: is
id: is-01m76qyyvpqww6t5tpbeadya7b
title: "PR #361 C3: Find Again clears the hold on an unvalidated runtime"
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
created_at: 2026-11-12T02:04:06.389Z
updated_at: 2026-11-12T03:38:11.551Z
started_at: 2026-11-12T02:04:20.523Z
closed_at: 2026-11-12T03:38:11.534Z
close_reason: "Fixed in f58eb702: isUnverified survives a search or choice (C3); RuntimeRecheckTests."
resolution: null
duplicate_of: null
---
High. RuntimeSelection.swift:69 (startSearch clears isRechecking). Review C3: https://github.com/jlevy/metabrowser/pull/361
