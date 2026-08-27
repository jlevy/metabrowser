---
type: is
id: is-01m12cvvwk6efgwv8rx56nxttb
title: "PR #86 review R8: no test exercises limit near GIT_LOG_MAX_LIMIT"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:59:02.034Z
updated_at: 2026-08-27T20:21:16.997Z
closed_at: 2026-08-27T20:21:16.997Z
close_reason: "Fixed in 3ad9113 on codex/unbounded-git-history (PR #86)"
resolution: null
duplicate_of: null
---
tests/test_git_history_session.py:303. Nothing covers client-settable page size vs fixed parser budget; a test at GIT_LOG_MAX_LIMIT would have caught R1. PR #86 comment 3873347493
