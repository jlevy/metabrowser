---
type: is
id: is-01m26z843xjntwh35dq9wc985c
title: Align KPress and embedded monospace typography
kind: task
status: in_progress
priority: 1
version: 2
labels:
  - release-hardening
  - design
dependencies: []
created_at: 2026-09-11T00:52:57.596Z
updated_at: 2026-09-11T00:53:01.063Z
---
Amend KPress PR #72 so inline and block monospace share one gentle solid border token, use zero radius through an overrideable code-radius token, and retain Metabrowser's compact inline padding. Remove dotted monospace borders. Align Metabrowser's downstream bridge and contract tests, refresh the static Menlo/Planetaire/Hack comparison, and verify both upstream and downstream before release installation.
