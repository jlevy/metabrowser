---
type: is
id: is-01m7jeqm49ppe20mk1g21tt05a
title: "PR #452 A1: compatibility guidance says nothing outside the repo consumes /api/* or CLI flags, but the macOS app does"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpct6qpjeqfpyetf79fef
hold: null
hold_until: null
created_at: 2026-11-16T15:13:42.024Z
updated_at: 2026-11-16T15:27:45.483Z
started_at: 2026-11-16T15:14:14.210Z
closed_at: 2026-11-16T15:27:45.482Z
close_reason: "Fixed in 024aadabe: Standing Compatibility Answers row for the app's four flags and GET /api/identity (floor bump + CHANGELOG note), Server APIs row qualified, macOS-app paragraph in docs/development.md, matching sentences in CONTRIBUTING.md and AGENTS.md."
resolution: null
duplicate_of: null
---
Medium. CONTRIBUTING.md:33-40 dropped the only CLI-flag protection; docs/development.md:361,:400 say /api/* is consumed only by the co-shipped client; arch-macos-app.md:51,:142-148 documents the separately installed app using --no-open --exit-on-eof --host --port and GET /api/identity with only a minimum-version gate. Review A on PR #452: https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5922214786
