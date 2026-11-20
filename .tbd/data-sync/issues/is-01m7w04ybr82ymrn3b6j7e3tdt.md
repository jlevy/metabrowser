---
type: is
id: is-01m7w04ybr82ymrn3b6j7e3tdt
title: "PR #649 A6: SDK contract session misses plugins.load interactions"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7w04vfg21q09dmkkdsmbzwp
hold: null
hold_until: null
created_at: 2026-11-20T08:11:14.168Z
updated_at: 2026-11-20T08:47:33.854Z
started_at: 2026-11-20T08:11:21.561Z
closed_at: 2026-11-20T08:47:33.854Z
close_reason: "fixed in 2558d772e: SDK contract session checks name+kind shared load, mixed-kind resolve with a failed module (mutation-checked), assets before exports; CI run 44703997703 green at 70f180380153ea5a6531e32e219e4ddf2d427883"
resolution: null
duplicate_of: null
---
Low. tests/dom/kpress-plugin-sdk-behavior.js:861-907. Review: https://github.com/jlevy/metabrowser/pull/649#pullrequestreview-5989412950
