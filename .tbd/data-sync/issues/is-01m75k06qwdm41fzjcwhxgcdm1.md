---
type: is
id: is-01m75k06qwdm41fzjcwhxgcdm1
title: "PR #351 B3: disabled Rendered chip can no longer appear; style and legend remain"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75jzxka1b2x14q44b46gh0y
hold: null
hold_until: null
created_at: 2026-11-11T15:18:09.915Z
updated_at: 2026-11-11T15:18:19.679Z
started_at: 2026-11-11T15:18:18.723Z
closed_at: 2026-11-11T15:18:19.678Z
close_reason: "fixed in a472de59: .chip:disabled rule and the session's '-' legend dropped; disabled flag and select() guard kept with a comment; session asserts a shown chooser never disables a chip"
resolution: null
duplicate_of: null
---
Low. diff-markdown.js:386; diff/styles.css:440-443; diff-markdown-session.js:15; cli-ui-diff-markdown.tryscript.md:50. PR #351, review B (https://github.com/jlevy/metabrowser/pull/351#pullrequestreview-5860745501).
