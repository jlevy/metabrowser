---
type: is
id: is-01m78a99jk907jdpngjf2h81rn
title: "PR #374 A1: shipped Metabrowser skill still teaches the removed stack keys"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78a8v8t7c3wp1sv22v0gqa8
hold: null
hold_until: null
created_at: 2026-11-12T16:43:33.842Z
updated_at: 2026-11-12T16:52:42.326Z
started_at: 2026-11-12T16:43:43.230Z
closed_at: 2026-11-12T16:52:42.323Z
close_reason: "fixed in 7d359509: SKILL.md:122-123 teaches N toward the stack top and P toward its base; also fixed plan-2026-10-01-github-pulls-tab.md:167-168 and research-2026-11-08-macos-app-packaging.md:182. Confirmed by make -o install lint-check and tests/test_public_hygiene.py. Disposition reply: https://github.com/jlevy/metabrowser/pull/374#issuecomment-6830048231"
resolution: null
duplicate_of: null
---
Medium. Review A on PR #374: https://github.com/jlevy/metabrowser/pull/374#pullrequestreview-5871435989. skills/metabrowser/SKILL.md:122 says to use Shift+J toward the stack base and Shift+K toward its top; layer 1 replaced those with N (toward the top) and P (toward the base). The skill ships in the sdist (devtools/check_distribution.py:252). Fix: replace the sentence with N and P, and fix any other current-behavior Shift+J, Shift+K, or Cmd+1/2/3 text in the repository; released CHANGELOG history stays.
