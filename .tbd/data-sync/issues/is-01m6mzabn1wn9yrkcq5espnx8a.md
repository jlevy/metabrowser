---
type: is
id: is-01m6mzabn1wn9yrkcq5espnx8a
title: Keep full-record polling phase when selected core POST is held
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m6mr68zq45xz8wz6das0q2x6
created_at: 2026-11-05T04:26:20.192Z
updated_at: 2026-11-05T07:18:59.341Z
closed_at: 2026-11-05T07:18:59.341Z
close_reason: "Implemented or diagnosed in Metabrowser PR #299 at 0d1b132d. Independent review, paired evidence, local make verify and all nine GitHub CI jobs passed; PR is mergeable. Merge remains with the owner."
resolution: null
duplicate_of: null
---
Candidate01 paired H77 captures improved selected core-description readiness but regressed full Conversation median from about 3082 ms to 3714 ms. The selected wait_core POST now lasts about 1.4–1.9 seconds; current client blocks polling until acknowledgement and then schedules its next normal one-second poll relative to that late response, shifting the observation phase. Hypothesis recorded before code: anchor the first normal poll after a held core acknowledgement to the existing one-second cadence from refresh POST start, without polling an unacknowledged request, overlapping GETs, or changing the cached-full path. Preserve ownership, visibility and cancellation. First prove the phase shift with a deterministic held-POST fake-clock test on the existing controller; retain RED, implement a minimal scheduling correction, and show GREEN before controlled browser comparison. This is only one contributor: cache-file publication was also approximately 0–300 ms later in most candidate pairs, and one candidate outlier was much slower; disk mtime only approximates atomic publication. No claim that cadence explains or fixes the whole measured regression. Parent feature mb-4ifm, H77 task mb-tgn3, exp-045.
