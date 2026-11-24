---
type: is
id: is-01m87bytyfh553qs4m16wbrykh
title: "PR #771 A3: comments say an input is kept only as a task list's box, but any checkbox is kept"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87bxfh1ymbm8c10h6rzs8gx
hold: null
hold_until: null
created_at: 2026-11-24T18:09:15.723Z
updated_at: 2026-11-24T18:30:13.607Z
started_at: 2026-11-24T18:15:10.336Z
closed_at: 2026-11-24T18:30:13.596Z
close_reason: "Fixed in 89eefc374: comments in inert_html.py, static/inert-html.js, pull-page.js and the inert-markdown golden's prose describe the kept shape, wherever the document writes a checkbox."
resolution: null
duplicate_of: null
---
Low. inert_html.py:57,187,704; static/inert-html.js:11,127,627; builtin_plugins/github/pull-page.js:31; tests/golden/cli-ui-inert-markdown.tryscript.md:16. Reword to describe the shape, not the source. PR #771, review https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6044731578
