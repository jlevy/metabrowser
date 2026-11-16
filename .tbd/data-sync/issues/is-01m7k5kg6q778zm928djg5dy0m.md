---
type: is
id: is-01m7k5kg6q778zm928djg5dy0m
title: "PR #485 A11: The workflow guard lists forbidden shapes instead of requiring the allowed one"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:24.182Z
updated_at: 2026-11-16T22:10:00.028Z
started_at: 2026-11-16T21:53:39.957Z
closed_at: 2026-11-16T22:10:00.020Z
close_reason: "Fixed in 83ef69fc3: mb-yqrs is an allowlist parsed with PyYAML: push of macos-v* tags only; the environment job has exactly contents: read, allowlisted actions, and only make macos-* targets and apps/macos/scripts; no workflow-level write permissions; no other workflow names the environment."
resolution: null
duplicate_of: null
---
Low. PLAN:488-492, :278-280; devtools/check_supply_chain.py:105-134. Fix: parse with PyYAML (on: reads as True) and require the allowed shape: push of macos-v* tags only, allowlisted actions and exactly contents: read in the environment job, no workflow-level write permissions, no other workflow naming the environment. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
