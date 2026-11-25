---
type: is
id: is-01m89ye591gbrd91c1yawma317
title: "Stack page: name each member's author on its member row, as the stack menu does"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T18:10:41.056Z
updated_at: 2026-11-25T18:10:41.056Z
---
Follow-up to mb-cm31 (PR #845, stacked on #843). The stack page's member rows (stack-member-row.js) are the stack menu's rows, which since #843 end with '· author'. The page draws no author yet: memberLines in stack-page.js has no author source. Options: the stack route's members name each record's author and avatar (pull_stack.py StackMember), or the page reads listedState like stackMemberAuthor. The route answer is the more reliable source on a cold load; cli-github-stack.txt is near its 2000-line golden budget, so split it by scenario if the envelope grows. Pin it in tests/dom/github-stack-page-session.js and the Chrome check.
