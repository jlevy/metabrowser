---
type: is
id: is-01m78aen8jb9kd7sbkrmnh8xyp
title: "PR #375 A3: a lone view is served with a key it cannot use"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ae0p02ghts4vw9h2vrmhp
hold: null
hold_until: null
created_at: 2026-11-12T16:46:29.648Z
updated_at: 2026-11-12T16:46:41.204Z
started_at: 2026-11-12T16:46:41.203Z
---
Medium. PR #375 review A (https://github.com/jlevy/metabrowser/pull/375#pullrequestreview-5871448143). check_view_keys runs before filters that shrink a kind's list to one view: _html_kind_views (server.py:4049) keeps only Source keyed s without active content (cli-untrusted.tryscript.md:90,109), and _folder_views (git/content_routes.py:1235-1244) keeps Overview alone keyed o. The browser draws a tab bar only for views.length > 1 (static/app.js:5928). Fix option (a): drop key from every entry when fewer than two views remain, in keymap.py, applied on the served path.
