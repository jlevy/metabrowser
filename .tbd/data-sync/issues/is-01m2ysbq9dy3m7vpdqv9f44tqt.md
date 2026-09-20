---
type: is
id: is-01m2ysbq9dy3m7vpdqv9f44tqt
title: "PR 217 R2: isolate environment-injected Git configuration"
kind: bug
status: closed
priority: 1
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2yrybwx5zatf3w9chdnfew6
hold: null
hold_until: null
created_at: 2026-09-20T06:51:50.444Z
updated_at: 2026-09-20T07:15:59.468Z
started_at: 2026-09-20T06:53:08.576Z
closed_at: 2026-09-20T07:15:59.467Z
close_reason: "Fixed in 70091d81: isolated Git policies scrub GIT_CONFIG and GIT_CONFIG_*."
resolution: null
duplicate_of: null
---
src/metabrowser/git/process.py:325 git_environment retains GIT_CONFIG_COUNT/KEY/VALUE and GIT_CONFIG_PARAMETERS despite isolate_user_config. Reproduced config lookup returning ambient value under ACQUISITION_POLICY. Scrub environment config only for isolated policies and test real Git behavior.

## Notes

Fixed locally in 70091d81 on PR 217; real Git config injection regressions passed with acquisition/process/CLI/goldens. Format/lint passed. Push, full gate, CI, and disposition pending. See mb-rldx.
