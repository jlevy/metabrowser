---
type: is
id: is-01m78a99jk907jdpngjf2h81rn
title: "PR #374 A1: shipped Metabrowser skill still teaches the removed stack keys"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78a8v8t7c3wp1sv22v0gqa8
hold: null
hold_until: null
created_at: 2026-11-12T16:43:33.842Z
updated_at: 2026-11-12T16:43:43.232Z
started_at: 2026-11-12T16:43:43.230Z
---
Medium. Review A on PR #374: https://github.com/jlevy/metabrowser/pull/374#pullrequestreview-5871435989. skills/metabrowser/SKILL.md:122 says to use Shift+J toward the stack base and Shift+K toward its top; layer 1 replaced those with N (toward the top) and P (toward the base). The skill ships in the sdist (devtools/check_distribution.py:252). Fix: replace the sentence with N and P, and fix any other current-behavior Shift+J, Shift+K, or Cmd+1/2/3 text in the repository; released CHANGELOG history stays.
