---
type: is
id: is-01m6c49dag1zyfrq3nzssh8md2
title: A /commit/ address with an encoded ref shows the untyped failure message
kind: bug
status: open
priority: 4
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-01T18:00:02.127Z
updated_at: 2026-11-01T18:00:02.127Z
---
Found 2026-11-01 while fixing mb-y1p5 in PR #275. /commit/refs%2Fheads%2Fmain still says Could not load this commit, because the encoded slash matches no route, where a short ID now gets a typed state.
