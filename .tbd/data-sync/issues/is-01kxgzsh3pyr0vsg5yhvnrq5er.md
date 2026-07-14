---
type: is
id: is-01kxgzsh3pyr0vsg5yhvnrq5er
title: Anchor Claude hooks to the project root
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
created_at: 2026-07-14T18:56:23.158Z
updated_at: 2026-07-14T18:57:32.368Z
closed_at: 2026-07-14T18:57:32.367Z
close_reason: Anchored every Claude hook to CLAUDE_PROJECT_DIR, added regression coverage, and passed all 611 tests and package gates
---
Use CLAUDE_PROJECT_DIR for every Claude hook command so session startup and compaction work from subdirectories; add configuration regression coverage.
