---
type: is
id: is-01m7hdfm8pb2wmm2d5nvgqp2vf
title: "PR #462 A1: Commits tab rows don't show the title-prefix rule; open question not recorded"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjk31aveb74wwdggthjpq
hold: null
hold_until: null
created_at: 2026-11-16T05:32:37.013Z
updated_at: 2026-11-16T06:03:40.080Z
started_at: 2026-11-16T05:32:43.293Z
closed_at: 2026-11-16T06:03:40.079Z
close_reason: "fixed in b846bf102 on claude/title-prefix-weight (#462): .git-graph-subject bold; Chrome before/after at 420 px: row 22 px, line 19.5 px, ellipsis kept; title-prefix-chrome expects 700; docs, CHANGELOG, parity row, plan Open Questions updated. CI run 43812004069 green at 9758ea748. Reply: https://github.com/jlevy/metabrowser/pull/462#issuecomment-6908742029"
resolution: null
duplicate_of: null
---
Medium. PR #462 review A round 1 (https://github.com/jlevy/metabrowser/pull/462#pullrequestreview-5915416972). src/metabrowser/static/styles.css:6254 (.git-graph-subject sets no weight); tests/dom/title-prefix-chrome.mjs:457 (pins the rest at 400); docs/design-system.md:1827; plan docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md:413-414 and Open Questions :546. Coordinator decision: make .git-graph-subject bold per the owner's words ("anywhere it's a commit title or a PR title", "bold as usual"), measure Commits rows before/after, update Chrome check, design system, CHANGELOG, plan Open Questions.
