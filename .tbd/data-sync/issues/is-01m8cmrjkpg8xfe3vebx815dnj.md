---
type: is
id: is-01m8cmrjkpg8xfe3vebx815dnj
title: Isolate pytest retention self-tests from operator options
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-26T19:19:19.925Z
updated_at: 2026-11-26T19:19:19.925Z
---
Mac verification uses failed-only retention in PYTEST_ADDOPTS. The transient-output self-tests then inherit it and lose the evidence they are meant to test for setup and teardown errors. Run these controlled nested sessions with the repository configuration. Keep the behavioral assertions for all failure phases, and leave normal operator flags effective in the outer run. Observed during validation of PR #380.
