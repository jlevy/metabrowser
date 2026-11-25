---
type: is
id: is-01m8ac52gphc8wse53q3k6j2gx
title: Age guard misses structural selectors; make the freshness rule win by construction
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T22:10:23.379Z
updated_at: 2026-11-25T22:10:23.379Z
---
Follow-up from review of #852 (mb-daxw). tests/test_age_single_source.py finds a rule that sets an age's ink by its subject's classes, so a rule that reaches an age by structure alone, e.g. .agents-row-line > span:last-child { color: var(--muted) }, passes it. None sets an age's ink today (a scan of every tracked stylesheet on 2026-11-25 found no class-less subject setting color, font-weight or font-variant-numeric that could match an age). Make it impossible by construction: give the freshness rule (:is(.age-live, ..., .age-old) in static/styles.css) !important on its ink, weight and numerals so no ordinary rule outranks it, and have the guard hold that the freshness rule keeps them and that no other rule uses !important on those properties. Measure in Chrome that no age's computed ink changes.
