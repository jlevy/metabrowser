---
type: is
id: is-01m7nb50wb8thbyrmhdh8yxnqx
title: "Folder header: an age that changes width (just now -> 1m ago) moves the values to its left; should the age hold a fixed slot like the run badge?"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-17T18:08:50.058Z
updated_at: 2026-11-17T18:08:50.058Z
---
Found by #521 (mb-j4ts): span.folder-header-summary refreshes one ROLLUP_WATCH_DEBOUNCE_MS after an inventory change; when the age text changes width the right-aligned summary shifts ~8 px. #521 fixed the test fixture only. Owner decision: hold a slot for the age (as the run badge does) or accept a value change moving its line.
