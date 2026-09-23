---
type: is
id: is-01m36k3ydz3tgxmycjj8wknzq5
title: "PR view: pull-request page with conversation, reviews, checks, and Files changed"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m35tapm6wjnn235hr3s669b7
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-23T07:36:39.614Z
updated_at: 2026-09-23T07:37:39.191Z
---
Implements the PR-view row: browser page for a pull request (description, labels, state, merge status, conversation, reviews, review comments listed with file and line, checks summary, Files changed via the merge-base comparison), reload and offline reopen, browserless session tests and goldens per AGENTS.md parity rules. Independent review, make verify, green CI.
