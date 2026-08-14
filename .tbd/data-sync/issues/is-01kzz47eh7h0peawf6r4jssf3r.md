---
type: is
id: is-01kzz47eh7h0peawf6r4jssf3r
title: "PR #35 review R1: Home and End steal caret movement in the Quick File input"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzz46ttyre78pjmkxynpfh3z
created_at: 2026-08-14T03:14:39.271Z
updated_at: 2026-08-14T03:32:01.749Z
closed_at: 2026-08-14T03:32:01.749Z
close_reason: "Fixed in 78ee53e: removed quick-file.first/last so Home and End stay with the query caret; arrow commands now wrap."
---
quick-file.first and quick-file.last register Home/End with allowInEditable: true in src/metabrowser/static/search_palette.js:702-739. The registry keydown listener is capture-phase (keyboard_shortcuts.js:554) and preventDefaults whenever a handler returns true, so a user editing the query cannot move the caret to line start or end. Contradicts the design-system rule that editable fields retain native browser behavior. Update tests/dom/search_palette_behavior.js:630-639.
