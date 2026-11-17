---
type: is
id: is-01m7kvt9j11bg98y2wxja97ctg
title: "PR #496 review B6: three places say ci-ok fails while main is red, stronger than the mechanism"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kvt6zsgb9m5xpanazw7prr
created_at: 2026-11-17T04:21:35.425Z
updated_at: 2026-11-17T04:23:04.890Z
closed_at: 2026-11-17T04:23:04.890Z
close_reason: "Fixed in 008a68b9: Goals, Risks, Q6, the section's bullet, and mb-oz36's title say a red main widens the matrix; ci_verdict never fails on MAIN_STATE alone."
resolution: null
duplicate_of: null
---
plan:49, :718-719, :755, and mb-oz36's title. The mechanism widens the matrix; ci-ok fails only on the run's own jobs.
