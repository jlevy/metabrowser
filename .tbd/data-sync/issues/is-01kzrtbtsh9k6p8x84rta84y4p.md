---
type: is
id: is-01kzrtbtsh9k6p8x84rta84y4p
title: Assess and publish Metabrowser v0.3.0 minor release
kind: task
status: in_progress
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-08-11T16:26:50.545Z
updated_at: 2026-08-11T16:57:08.161Z
---
Review all user-visible changes since v0.2.0, triage outstanding defects for release blockers, validate the filtering/search stabilization release, prepare accurate v0.3.0 notes, run the complete release gate, publish the GitHub release, verify PyPI artifacts and public smoke tests, and confirm CI.

## Notes

Release audit complete: 67 commits since v0.2.0, with filtering, Quick File, KPress 0.3.2, design, security documentation, Agent Skill, and workflow improvements. Fixed the one headline blocker by making Live a uniform 90-second mtime window for every file while retaining agent-log active/tailing behavior. README, CLI, installation docs, skill metadata, and related records now describe a general file browser rather than an artifact browser. Full make verify passes (859 tests, 28 golden scenarios, lint/types, hygiene, audits, distribution and wheel smoke checks). Real-browser checks pass for Live expiry and ordinary-file updates, compound filters, keyboard traversal, Quick File, Markdown, JSONL, direct links, themes, responsive layout, and console health. Remaining watcher-overflow and load-sensitive-test beads are pre-existing and explicitly deferred; neither warrants holding v0.3.0. Next: commit, PR, exact-commit CI, GitHub release, PyPI and skill smoke verification.
