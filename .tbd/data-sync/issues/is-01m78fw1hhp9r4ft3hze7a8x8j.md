---
type: is
id: is-01m78fw1hhp9r4ft3hze7a8x8j
title: metab --doctor reports a state home that differs between a Terminal and the app's servers
kind: task
status: open
priority: 2
version: 9
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:11.088Z
updated_at: 2026-11-26T08:37:20.273Z
started_at: 2026-11-26T08:35:34.364Z
---
Phase 0 (plan: Key Decision 7, The macOS App). The first revision had the app read the home variables from the login shell. main decided against that for the cache and configuration homes: the app passes none of STORAGE_OVERRIDES and only what it was launched with of LAUNCH_STORAGE_OVERRIDES (cli/doctor.py), pinned by tests/test_macos_app_pins.py, and --doctor warns when a Terminal's home differs from the app's servers'. The state home's variables (METABROWSER_STATE_DIR, XDG_STATE_HOME) are passed as launched and are not in that check, because they held only the event log. With the plugin registry in the state home, a user who exports XDG_STATE_HOME only in a shell profile gets one registry in Terminal and another in the app. Extend the doctor's check to the state home, with the same wording and remedy, and its test.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
