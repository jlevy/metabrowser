---
type: is
id: is-01m87byxwhjadky01cr1d5zjzp
title: "PR #771 A4: no golden records a kept box; add task list and raw checkbox variants to HOSTILE_README"
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
created_at: 2026-11-24T18:09:18.717Z
updated_at: 2026-11-24T18:30:16.713Z
started_at: 2026-11-24T18:17:08.306Z
closed_at: 2026-11-24T18:30:16.676Z
close_reason: "Fixed in 7112466b7: HOSTILE_README gains a task list and raw checkbox variants and the both-sides test asserts the five boxes; the session gets its own checkbox input (boxes), recorded in cli-ui-inert-markdown.tryscript.md. A mutation that drops disabled from the JS box now fails the session."
resolution: null
duplicate_of: null
---
Low. tests/dom/inert-html-session.js:244-251; tests/test_inert_html.py:34 (HOSTILE_README); tests/fixtures/inert-html-kpress-tree.json. Add a task list and raw checkbox variants, re-record. PR #771, review https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6044731578
