---
type: is
id: is-01m89xq5vphwjb7edgf2xtnncj
title: "PR #841 A4: pin recipe uses jq -er"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m89xprnt4aby23f09h7bg3v9
hold: null
hold_until: null
created_at: 2026-11-25T17:58:07.985Z
updated_at: 2026-11-25T18:14:54.587Z
started_at: 2026-11-25T17:58:16.155Z
closed_at: 2026-11-25T18:14:54.586Z
close_reason: fixed in a6635aeb80e35d86c1190fa5a0af977e84144832; disposition reply https://github.com/jlevy/metabrowser/pull/841#issuecomment-7170643113
resolution: null
duplicate_of: null
---
Low. skills/metabrowser/SKILL.md:683, tests/golden/cli-skill-recipes.tryscript.md:254. Use jq -er and point at .record.unavailable.comparison. Review: https://github.com/jlevy/metabrowser/pull/841#pullrequestreview-6062463825
