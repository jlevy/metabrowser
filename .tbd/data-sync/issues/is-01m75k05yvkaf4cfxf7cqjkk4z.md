---
type: is
id: is-01m75k05yvkaf4cfxf7cqjkk4z
title: "PR #351 B1: merging #349's tip breaks diff-markdown-behavior.js (add() without toggle)"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75jzxka1b2x14q44b46gh0y
hold: null
hold_until: null
created_at: 2026-11-11T15:18:09.111Z
updated_at: 2026-11-11T15:18:19.041Z
started_at: 2026-11-11T15:18:18.064Z
closed_at: 2026-11-11T15:18:19.040Z
close_reason: "fixed in merge fd8a50ad: #349's sanitizer-retry test passes toggle2 and asserts the chooser stays on both retryable sanitizer failures; diff-markdown-behavior.js passes on the merged tree"
resolution: null
duplicate_of: null
---
High. diff-markdown.js:574-581, :630; tests/dom/diff-markdown-behavior.js:525-526 at 4e4f4ca (ee1289fb). PR #351, review B (https://github.com/jlevy/metabrowser/pull/351#pullrequestreview-5860745501).
