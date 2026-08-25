---
type: is
id: is-01m0vsbcvvw9t96g5a73pkpb5d
title: Measure Git history cost and define structural budgets
kind: task
status: open
priority: 1
version: 3
labels:
  - release:v0.8.0
dependencies:
  - type: blocks
    target: is-01m0vscnvzcjatq9nd43zvqnwa
  - type: blocks
    target: is-01m0vscy963c6aphv6ga8wmxww
parent_id: is-01m0ghvrnps0hh3m8d28xvfn2j
created_at: 2026-08-25T06:22:32.826Z
updated_at: 2026-08-25T06:23:23.429Z
---
Build deterministic Git-history corpora at multiple depths and branch shapes; measure API latency, skip-depth growth, payload bytes, retained client data, DOM nodes, renderer memory, append/layout cost, scrolling, selection, and deep-route restoration in a real browser. Establish the cost shape and record measurements beside every resulting budget. Add stable contract assertions for structural bounds rather than wall-clock CI tests.
