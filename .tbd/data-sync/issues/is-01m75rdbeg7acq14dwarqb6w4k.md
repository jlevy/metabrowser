---
type: is
id: is-01m75rdbeg7acq14dwarqb6w4k
title: Spinner-free PR refresh and prefetch
kind: epic
status: open
priority: 1
version: 4
labels: []
dependencies: []
child_order_hints:
  - is-01m75rdbxzcrqfwpk9s3bgwvx4
  - is-01m75rdcd4ydy6gcf8x52wzrgt
  - is-01m75rdcxakv4vm7ey8fvt1d72
created_at: 2026-11-11T16:52:43.599Z
updated_at: 2026-11-11T16:52:45.096Z
---
User request 2026-11-11: reopening the browser and expanding a PR must not show a spinner; open PRs show the cached version and refresh in the background; no spinner over rendered content; no 'may be out of date' (always refreshing, name a problem only when a refresh cannot run); prefetch a reasonable amount; a very subtle animation on names being refreshed. Two stacked PRs: PR 1 presentation (claude/pr-refresh-without-spinners), PR 2 event-based freshness, prefetch tiers and rate-limit governor (claude/pr-freshness-prefetch). Design: scratchpad freshness/report.md from the investigation of bdcfedd4.
