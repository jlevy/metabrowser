---
type: is
id: is-01m868mqm01mnzdy18sf7spn2g
title: "Guided reviews in the agent skill: a draft check and a skill section"
kind: feature
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-24-guided-reviews-skill.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T07:52:04.457Z
updated_at: 2026-11-24T21:10:41.832Z
started_at: 2026-11-24T21:10:17.417Z
---
Teach the metabrowser agent skill to write, publish, and refresh a pull request's guided review, and give it a metab check of a draft guide before publishing. Plan: docs/project/specs/active/plan-2026-11-24-guided-reviews-skill.md.

#785 ships the skill's Write a Guided Review section (the six review concerns, a block skeleton held to parse_guide, the YAML and pin rules, and recipes to publish, confirm, and refresh a guide), its checks in tests/test_skill_commands.py, the plan, and the changelog fragment.

## Notes

Remaining for Phase 1, after #785:
- The guided-review-check route (/api/plugin/github/guided-review-check), with its parity row, the route map entry, and a golden on the GitHub stand-in.
- Its recipes in the skill's Write a Guided Review section and in tests/golden/cli-skill-recipes.tryscript.md, with a mutation that skips the check failing.
- The person-facing part in docs/working-with-agents.md ("ask an agent to add a guided review").
- The handoff line in AGENTS.md ("add or refresh the pull request's guided review").
Open question in the plan: whether the check reads the draft as a file in the checkout or as the description to publish.
