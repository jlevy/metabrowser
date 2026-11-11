---
type: is
id: is-01m74t2n82a86hk04bzaknsc6r
title: "PR #346 A3: a refused comparison request's reason disappears after the next poll"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74t21pvwps4wh189z73rspr
hold: null
hold_until: null
created_at: 2026-11-11T08:02:35.905Z
updated_at: 2026-11-11T08:21:20.055Z
started_at: 2026-11-11T08:02:47.196Z
closed_at: 2026-11-11T08:21:20.054Z
close_reason: "Fixed in 9c625f4e (option 1): the controller keeps comparisonRefusal until the page asks again; describePull shows it as the header message on Changes after a later read clears the error, so the docs' claim holds. Confirmed by the session's refusal steps and github-pull-page-mount-behavior.js (.github-pull-message after the poll)."
resolution: null
duplicate_of: null
---
Low. The refusal reason lives only in error, cleared by the next 200 GET (pull-page.js:1258), though CHANGELOG.md:10, docs/reviewing-pull-requests.md:87, docs/command-line.md:387, skills/metabrowser/SKILL.md:90, plan-2026-10-01-github-pulls-tab.md:724 say Changes reports it. Fix (pick one): keep the refusal in its own field cleared on a new attempt, or soften the docs. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5855482052 (PR #346, review A, round 1).
