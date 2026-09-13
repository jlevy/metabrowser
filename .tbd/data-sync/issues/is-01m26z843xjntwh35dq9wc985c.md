---
type: is
id: is-01m26z843xjntwh35dq9wc985c
title: Align KPress and embedded monospace typography
kind: task
status: closed
priority: 1
version: 3
labels:
  - release-hardening
  - design
dependencies: []
created_at: 2026-09-11T00:52:57.596Z
updated_at: 2026-09-11T08:26:21.365Z
closed_at: 2026-09-11T08:26:21.364Z
close_reason: "KPress PR #72 is green at 10d23bc6 and downstream Metabrowser bridges the published variables with pinned-0.3.5 fallbacks. Inline and block monospace now share the gentle solid border token, zero-radius variable, and compact padding; contract tests and the Menlo/Planetaire/Hack comparison are updated."
resolution: null
duplicate_of: null
---
Amend KPress PR #72 so inline and block monospace share one gentle solid border token, use zero radius through an overrideable code-radius token, and retain Metabrowser's compact inline padding. Remove dotted monospace borders. Align Metabrowser's downstream bridge and contract tests, refresh the static Menlo/Planetaire/Hack comparison, and verify both upstream and downstream before release installation.
