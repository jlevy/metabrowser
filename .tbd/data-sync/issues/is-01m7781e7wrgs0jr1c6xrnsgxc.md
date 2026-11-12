---
type: is
id: is-01m7781e7wrgs0jr1c6xrnsgxc
title: "Source view: appended text does not normalize CR or CRLF as the first render does"
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T06:45:04.891Z
updated_at: 2026-11-12T06:45:04.891Z
---
Found while making #367: the source view's Load more path appends text without the line-ending normalization of the first render, so a file with lone CRs shows its appended part as one line, and copying it gives mixed line endings. Pre-existing on main.
