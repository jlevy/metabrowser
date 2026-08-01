---
type: is
id: is-01kyxyyy0pj8hddy6584peh7yf
title: "Spike 1: specify and fixture fuzzy filename ranking"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies:
  - type: blocks
    target: is-01kyxyzjxyh94a9re1jps0mv23
parent_id: is-01kyxyb67v18br7jm7w8mrwss5
created_at: 2026-08-01T06:07:41.077Z
updated_at: 2026-08-01T06:26:17.107Z
closed_at: 2026-08-01T06:26:17.106Z
close_reason: Documented the Phase 1 fuzzy ranking contract and review fixtures; make verify passes.
---
Define the reviewable ranking contract before scorer code. Add the fuzzy-file-ranking spike report and a machine-readable scenario fixture covering exact and prefix basename matches, basename versus parent-directory matches, boundaries, camel case, punctuation, gaps, path queries, repeated characters, case, Unicode, and deterministic ties. Document normalization, eligibility, match ranges, the named comparison vector, ordering rationale, and the checklist for recording before-and-after behavior when tuning. Done when a maintainer can explain every fixture winner without reading implementation code.
