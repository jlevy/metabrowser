---
type: is
id: is-01kyxrv9b8sz53y818cbdj1h0f
title: Evaluate removing the redundant Highlight.js theme stylesheet
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-08-01T04:20:50.151Z
updated_at: 2026-08-01T04:20:50.151Z
---
Deferred from PR #19 review suggestion S1. Metabrowser now owns every Highlight.js semantic color; assess inlining the two surviving layout rules and removing vendor/highlight-github.min.css, its request, manifest entry, and async loading path in a focused supply-chain change.
