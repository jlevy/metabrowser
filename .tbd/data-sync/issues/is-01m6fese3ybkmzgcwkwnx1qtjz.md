---
type: is
id: is-01m6fese3ybkmzgcwkwnx1qtjz
title: "PR #283 A1: UI pull-page golden too large for tryscript matcher (make test red)"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
hold: null
hold_until: null
created_at: 2026-11-03T01:01:16.286Z
updated_at: 2026-11-03T01:53:58.603Z
started_at: 2026-11-03T01:33:01.371Z
closed_at: 2026-11-03T01:53:58.602Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: A1 session printed in two parts; all tryscript goldens pass"
resolution: null
duplicate_of: null
---
High. Review A https://github.com/jlevy/metabrowser/pull/283#pullrequestreview-5745443078. tests/golden/cli-ui-github-pull-page.tryscript.md, tests/dom/github-pull-page-session.js:842-901. Split the session output across two commands and re-record.
