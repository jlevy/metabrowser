---
type: is
id: is-01m6rsf8q3wnc8b005gk8q8r14
title: Install and smoke-test the verified Metabrowser stack build
kind: task
status: closed
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m6qd2d538c6k0psmpr1sh0d7
hold: null
hold_until: null
created_at: 2026-11-06T16:01:07.298Z
updated_at: 2026-11-06T16:03:18.186Z
started_at: 2026-11-06T16:01:40.625Z
closed_at: 2026-11-06T16:03:18.185Z
close_reason: Default installation and local preview verified.
resolution: null
duplicate_of: null
---
Replace both default CLI entry points with the verified stack-head wheel, check the installed skill, and restore the local preview.

## Notes

Installed 0.11.1.dev1175+122af86c as both default commands from the verified PR #307 wheel with locked dependencies. The stack head includes current main. The installed agent skill matches the same source. Restored the checkout preview on 8864, matched the served PR page asset to the wheel, and used the built-in browser to verify that a cold direct link to #307 fetched, rendered, and persisted an owner-only JSON record.
