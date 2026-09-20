---
type: is
id: is-01m2ysbq9dy3m7vpdqv9f44tqt
title: "PR 217 R2: isolate environment-injected Git configuration"
kind: bug
status: closed
priority: 1
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2yrybwx5zatf3w9chdnfew6
hold: null
hold_until: null
created_at: 2026-09-20T06:51:50.444Z
updated_at: 2026-09-20T15:45:58.933Z
started_at: 2026-09-20T06:53:08.576Z
closed_at: 2026-09-20T07:15:59.467Z
close_reason: "Fixed in 70091d81: isolated Git policies scrub GIT_CONFIG and GIT_CONFIG_*."
resolution: null
duplicate_of: null
---
src/metabrowser/git/process.py:325 git_environment retains GIT_CONFIG_COUNT/KEY/VALUE and GIT_CONFIG_PARAMETERS despite isolate_user_config. Reproduced config lookup returning ambient value under ACQUISITION_POLICY. Scrub environment config only for isolated policies and test real Git behavior.

## Notes

Fixed locally in 70091d81 on PR 217; real Git config injection regressions passed with acquisition/process/CLI/goldens. Format/lint passed. Push, full gate, CI, and disposition pending. See mb-rldx.

2026-09-20: no longer pending. The fix was pushed — 70091d81 is the current head of PR #217
(gh pr view 217 --json headRefOid) — and CI is green on it (gh pr checks 217: distribution,
lint, stack-integration, test 3.12/3.13/3.14/3.14t all pass).
