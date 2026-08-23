---
type: is
id: is-01m0r4pm8rxaq5jnefyxnkymtj
title: Make browser responsiveness a reusable performance-loop gate
kind: feature
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01m0qzc5f2d4adgvcs5sb0zqb2
created_at: 2026-08-23T20:23:57.463Z
updated_at: 2026-08-23T21:34:07.821Z
closed_at: 2026-08-23T21:34:07.820Z
close_reason: Added a reusable web-performance contract, TOML budgets, evidence validation, hard gates, comparison rules, navigation-time browser telemetry, scenario loops, documentation, and tests. Metabrowser's record/compare workflow now uses it.
---
Extract a reusable web-performance contract for visible navigation-time measurement, bounded responsiveness telemetry, standard loading and visual metrics, app-specific adapters, configurable budgets, and record/compare failures. Wire Metabrowser's exploration loop to it so hidden, late, interaction-free, or over-budget runs cannot be accepted.
