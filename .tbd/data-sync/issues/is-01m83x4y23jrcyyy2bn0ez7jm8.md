---
type: is
id: is-01m83x4y23jrcyyy2bn0ez7jm8
title: Measure an hour of real GitHub browsing against AUTOMATIC_CORE_PER_HOUR and SPECULATIVE_CORE_PER_HOUR
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-23T09:52:43.584Z
updated_at: 2026-11-25T03:54:55.111Z
---
From the #737 review A fixes: SPECULATIVE_CORE_PER_HOUR (100 of 300) and the ceiling itself are set by arithmetic, not by measurement. Record governor.ceiling.hour_used and speculative_hour_used (GET pulls-prefetch, metab --api) over a few real hour-long sessions on busy repositories, put the result beside the constants in gh_budget.py, and close the plan's open question on it. Also decide whether self_ceiling needs an on-screen notice.
