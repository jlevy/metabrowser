---
type: is
id: is-01kyh33rs5ne1wek29s6tqzxas
title: Hide folder tab bar when no README view is available
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-07-27T06:10:06.244Z
updated_at: 2026-07-27T06:26:29.087Z
closed_at: 2026-07-27T06:26:29.086Z
close_reason: Implemented conditional README view advertisement, verified no-tab Treemap rendering live, passed make verify with 748 tests, pushed commit 16c9949, and confirmed final PR checks green (Bugbot skipped).
---
Folder envelopes currently advertise the README view even when readme_path is empty, causing a useless Treemap/README tab bar and an empty README view. Omit the README view when the folder has no direct-child README so the existing single-view renderer shows the Treemap without any tab bar.
