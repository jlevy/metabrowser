---
type: is
id: is-01m7b2wssq4q3z87p7yxs240er
title: "PR header: keep unchanged nodes across repaints (identity, badge, chips, icons)"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-13T18:32:07.734Z
updated_at: 2026-11-13T18:44:58.288Z
---
Found by the avatar-flicker sweep (#399). `paintStateRow` and `paintHeader` in `builtin_plugins/github/pull-page.js` rebuild unchanged nodes on every paint: the identity, the badge with #370's badge sizers, the branch chips with their copy buttons, the title's state-icon SVG, the GitHub mark, and the labels. Every paint includes tab switches and the 1 s polls while a refresh runs.

Nothing paints blank now that avatars are eager, but it is DOM churn. Suspected, not measured: a tooltip or hover on a header chip may be disturbed when the poll replaces that node.

The natural place for the fix is #370's header rewrite (the performance session's `claude/perf-layout`): keep a node when its inputs are unchanged.

Done when:
- the header keeps unchanged nodes across paints;
- a browserless test pins node reuse per paint;
- the hover and tooltip case is measured.

## Notes

Merge note (2026-11-13): #399 passes { loading: "eager" } to the header authorLabel call in paintStateRow; #370 rewrites the next line (wraps the action in span.github-pull-action). Whichever merges second takes #370's text and keeps the eager argument in its authorLabel call. Only that hunk and CHANGELOG conflict.
