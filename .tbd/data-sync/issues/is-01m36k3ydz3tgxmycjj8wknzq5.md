---
type: is
id: is-01m36k3ydz3tgxmycjj8wknzq5
title: "PR view: pull-request page with conversation, reviews, checks, and Files changed"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m35tapm6wjnn235hr3s669b7
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-23T07:36:39.614Z
updated_at: 2026-09-24T13:21:27.610Z
closed_at: 2026-09-24T13:21:27.609Z
close_reason: "PR view: PR #233 (codex/v012-pr-view, head 8e5be947, above #232). The pull-request page (conversation, reviews, review comments, checks, Files changed via the merge-base comparison, freshness and refresh, head offer after a fallback) renders comment Markdown through a strict two-layer allowlist. An independent review and a security review found issues, all fixed. CI green on all nine checks."
resolution: null
duplicate_of: null
---
Implements the PR-view row: browser page for a pull request (description, labels, state, merge status, conversation, reviews, review comments listed with file and line, checks summary, Files changed via the merge-base comparison), reload and offline reopen, browserless session tests and goldens per AGENTS.md parity rules. Independent review, make verify, green CI.
