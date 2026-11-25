---
type: is
id: is-01m89ye9z7j24hgpjjjxsq3g7v
title: "Stack page size line: commits and bytes, as a pull request's size line has them"
kind: feature
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T18:10:45.860Z
updated_at: 2026-11-25T18:10:45.860Z
---
Follow-up to mb-cm31 (PR #845). The stack page's size line is the change size line of the files alone ('1 file changed') because the stack route answers no commit count or diff bytes. A pull request's says '2 commits · 36 files changed · 1.8 MB compressed (6.2 MB raw diff)'. Add the counts to the stack's answer (or a stack size route), draw them with changeSizeLine, and pin them in the stack goldens.
