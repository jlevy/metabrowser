---
type: is
id: is-01m12cvsb4asy619ax2e0h3hsd
title: "PR #86 review R1: limit=1000 overruns fixed parser budget, returns HTTP 500"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:58:59.427Z
updated_at: 2026-08-27T20:21:16.944Z
closed_at: 2026-08-27T20:21:16.933Z
close_reason: "Fixed in 3ad9113 on codex/unbounded-git-history (PR #86)"
resolution: null
duplicate_of: null
---
src/metabrowser/git/history.py:585. GIT_HISTORY_SESSION_PARSER_MAX_BYTES (128 KiB) is charged against the cumulative page bytes, but limit can be up to GIT_LOG_MAX_LIMIT=1000. HistoryParserError -> GitError -> 500 for a legal request. Derive budget from page_size or bound per record. PR https://github.com/jlevy/metabrowser/pull/86 comment 3873346146
