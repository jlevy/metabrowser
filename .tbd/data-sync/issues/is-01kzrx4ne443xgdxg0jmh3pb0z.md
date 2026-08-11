---
type: is
id: is-01kzrx4ne443xgdxg0jmh3pb0z
title: Keep filter selections transient
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-11T17:15:21.411Z
updated_at: 2026-08-11T17:23:45.023Z
closed_at: 2026-08-11T17:23:45.022Z
close_reason: Filter state now starts from defaults on every page load, never writes mb.prefs, and removes the obsolete filters preference. Regression coverage and a real-browser reload check confirm filters reset while dark mode persists.
---
Filter selections are visit-specific view state, but filter_state.js restores and writes them through the host-wide mb.prefs cookie API. This makes unrelated browser sessions and served roots inherit stale filtering. Initialize filters from defaults on every page load, never write them to preference storage, expire the obsolete filters preference, and preserve persistence only for durable appearance settings such as theme and fonts.
