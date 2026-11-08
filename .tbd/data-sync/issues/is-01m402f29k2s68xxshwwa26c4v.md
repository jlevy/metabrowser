---
type: is
id: is-01m402f29k2s68xxshwwa26c4v
title: Execute the full v0.12 QA runbook on a pinned post-landing candidate
kind: task
status: in_progress
priority: 1
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
hold: null
hold_until: null
created_at: 2026-10-03T05:05:53.458Z
updated_at: 2026-11-08T09:55:55.423Z
started_at: 2026-11-08T03:02:07.630Z
---
Run setup/doctor including negative controls, full make verify, admitted Git/macOS/live-GitHub tiers, refusal checks, plain-folder features in real browsers, acquisition/cache/pins/trust, GitHub URLs and PR pages, refresh/ref switching/offline reopening, and regression comparisons. Record step-level pass/fail/blocked/untested. Keep caches and temporary outputs on external scratch and durable evidence outside scratch.

## Notes

Installed H2 (a2bb0d29a, version 0.11.1.dev1280+a2bb0d29a) negative setup check passed: isolated child PATH excludes gh; Pulls returns typed gh_missing with one visible setup message and official install link, plus clipped polite live announcement. Files and local Commits continue functioning; selected afaf rendered 4 files with no busy state. Initial 0755 fixture cache/config correctly refused, then fixture-only permissions corrected to0700 before test. No auth, global PATH or normal cache/config changed. Receipt: metabrowser-installed-gh-missing-20261108/functional-receipt.json with raw pulls.json. Temporary8917 server verified/stopped SIGINT130 and tab closed. Functional scope only; full pinned release runbook remains open.
