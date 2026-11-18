---
type: is
id: is-01m7r96j1rqavpv1pgx5fh6nwc
title: The first screen asks for rendered files the route will refuse for size
kind: task
status: open
priority: 4
version: 1
labels: []
dependencies: []
parent_id: is-01m7pfyxz015mfas5phhvtqz33
created_at: 2026-11-18T21:32:26.527Z
updated_at: 2026-11-18T21:32:26.527Z
---
Found by review C10 of PR #557. The first screen spends one of its FIRST_SCREEN_MARKDOWN places on a file such as package-lock.json that the route refuses as too_large (60 of this repository's 456 real JSON pairs). The manifest carries no blob sizes for the page to skip them by. Give the manifest's sides their sizes, or let the page skip a file whose changed lines already exceed a bound, and measure the first screen again.
