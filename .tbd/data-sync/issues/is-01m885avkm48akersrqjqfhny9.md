---
type: is
id: is-01m885avkm48akersrqjqfhny9
title: "Reader-message check: tell an exception's text by its type, not its receiver's name"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m87ky2a36j5yg4pf9827xxd6
created_at: 2026-11-25T01:32:44.008Z
updated_at: 2026-11-25T01:32:44.008Z
---
From review A1 on PR #801 (https://github.com/jlevy/metabrowser/pull/801#pullrequestreview-6049962996), the one shape left after the cheap ones were closed. rule_exception_text accepts a .message read when its receiver is a catch binding or is named like an error (ERROR_NAME); the same read under another name passes, as static/navigation.js:1033-1038 shows (legitimate there, accepted by name). Closing it needs flow or type information the literal extractor does not have: follow a caught binding through locals and parameters, or read JSDoc types.
