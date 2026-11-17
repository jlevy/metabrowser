---
type: is
id: is-01m7nye9z6v3jy9eah9ah2102t
title: "Skill: fix recipes that fail as written, and add a drift test binding SKILL.md to the CLI"
kind: task
status: open
priority: 1
version: 1
labels:
  - skill
  - alpha
dependencies: []
created_at: 2026-11-17T23:45:57.220Z
updated_at: 2026-11-17T23:45:57.220Z
---
From the 2026-11-17 end-to-end skill review (attic/skill-review): PR recipes omit --format json (jq fails); no checkout recipe (uncached PR needs pull-refresh POST); failure detection parses prose instead of .state/.last_refresh.outcome; --remote example lacks --no-open/backgrounding; /api/stream claim wrong; 'one head per server' contradicts reuse (pin is mutable); address list lacks /pull/<n>/files/<path>; --show /commit/HEAD exits 0. Add tests/test_skill_commands.py (every --flag exists, every /api route registered) and a golden running the PR recipe on the file:// fixture.
