---
type: is
id: is-01m88dzjcpjtvd7dqk13r47nae
title: "check_parity: git-commit-history-session.js exits SIGSEGV under NODE_V8_COVERAGE at high load"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T04:03:51.311Z
updated_at: 2026-11-25T04:03:51.311Z
---
During make lint-check on claude/stack-review (node v24.19.0, load ~330, pytest running concurrently), node tests/dom/git-commit-history-session.js exited -11 with no output and no crash report, failing three git.* parity rows. It exited 0 twice when rerun alone under coverage. The mechanism is unknown: find it (core dump, ulimit -c, repeat under load) rather than rerunning.
