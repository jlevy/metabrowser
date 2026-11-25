---
type: is
id: is-01m88754ykaf22y6zjm6knjmxz
title: Collection references to a pull request, a file as a pull request changes it, and a commit
kind: feature
status: in_progress
priority: 2
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m8806zrnxn9jwj89hffd2yv7
hold: null
hold_until: null
created_at: 2026-11-25T02:04:34.103Z
updated_at: 2026-11-25T10:55:14.716Z
started_at: 2026-11-25T07:53:39.977Z
---

## Notes

Built on claude/stack-reference-kinds, PR #834 (draft, stacked on #829 in native stack 809).
Decisions where the plan left room: one CollectionReference model with optional pull and commit, `kind` derived; every answer carries every field (kind, pull, commit, comparison, target), null where the kind has none; a {pull} href is /pull/N and its stack place prefers the stack holding the guide's pull request; a {commit} href is /commit/<sha>; a {pull, path} is drawn from its pull request's own comparison routes, one diff-source run per cited pull request (unmeasured, noted at MAX_REFERENCES).
Deviation: a {pull, path} this copy has not read links to that file in its pull request's Changes (which loads it), not the pull request alone; recorded in the plan's status line.
Chrome check tests/dom/github-guided-review-kinds-chrome.mjs found a row's text ran its parts together; rows now put a space between parts.
2026-11-25: merged #829's moves upward (085ce2637, then 3af9f4f1e as 009a42ff5); the stack conflicts with main in #829's pull-page.js (createStackMenu's deps JSDoc: main's `menus` against the stack's `wholeStack`), so ci-ok stays red on every layer above #822 until #829 merges main. #838 (mb-ri96) is stacked on this layer.
