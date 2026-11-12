---
type: is
id: is-01m76qz16gf3gdp13xxjb32c09
title: "PR #361 C5: a permission-only repair never triggers discovery"
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
created_at: 2026-11-12T02:04:08.783Z
updated_at: 2026-11-12T03:38:28.958Z
started_at: 2026-11-12T02:04:22.478Z
closed_at: 2026-11-12T03:38:28.943Z
close_reason: "Fixed in f58eb702: FileFingerprint.mode (C5); RuntimeRecheckTests."
resolution: null
duplicate_of: null
---
Medium. FileWatch.swift:27 (fingerprint omits the mode). Review C5: https://github.com/jlevy/metabrowser/pull/361
