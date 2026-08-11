---
type: is
id: is-01kyxrv9b8sz53y818cbdj1h0f
title: Evaluate removing the redundant Highlight.js theme stylesheet
kind: task
status: closed
priority: 3
version: 3
labels: []
dependencies: []
created_at: 2026-08-01T04:20:50.151Z
updated_at: 2026-08-01T04:53:10.653Z
closed_at: 2026-08-01T04:53:10.652Z
close_reason: "Completed in a60f97b: removed the redundant vendored Highlight.js theme, moved its two surviving layout rules into host CSS, and updated asset, supply-chain, and palette contracts."
---
Deferred from PR #19 review suggestion S1. Metabrowser now owns every Highlight.js semantic color; assess inlining the two surviving layout rules and removing vendor/highlight-github.min.css, its request, manifest entry, and async loading path in a focused supply-chain change.
