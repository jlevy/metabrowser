---
type: is
id: is-01m7w04wfvxcw30c0fw0ge0dqr
title: "PR #649 A2: refused override removes the shadowed built-in and cascades to folder"
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
created_at: 2026-11-20T08:11:12.251Z
updated_at: 2026-11-20T08:47:32.317Z
started_at: 2026-11-20T08:11:20.169Z
closed_at: 2026-11-20T08:47:32.317Z
close_reason: "fixed in b956c4ad1/b95b819a6: discover_plugins restores the shadowed plugin when its replacement is refused and resolves again; tests test_a_refused_override_keeps_the_plugin_it_would_replace, ..._on_a_cycle_..., golden case in cli-plugins-requires; CI run 44703997703 green at 70f180380153ea5a6531e32e219e4ddf2d427883"
resolution: null
duplicate_of: null
---
Medium. src/metabrowser/plugin_loader/discovery.py:229-232. Review: https://github.com/jlevy/metabrowser/pull/649#pullrequestreview-5989412950
