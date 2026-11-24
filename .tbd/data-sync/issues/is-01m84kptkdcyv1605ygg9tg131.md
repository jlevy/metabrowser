---
type: is
id: is-01m84kptkdcyv1605ygg9tg131
title: The Copilot coding agent's author reads copilot-swe-agent[bot] through GraphQL and Copilot through REST
kind: bug
status: closed
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T16:26:58.540Z
updated_at: 2026-11-23T20:48:53.950Z
started_at: 2026-11-23T16:27:04.308Z
closed_at: 2026-11-23T17:29:17.234Z
close_reason: "Fixed in #762 (6fd2b2092): _REST_BOT_LOGINS maps GraphQL copilot-swe-agent to REST Copilot (one account, id 198982749, per reads of makr-code/ThemisDB#8365 and t-h-omy/Volcanae#396 on 2026-11-23). The app-authored test's new Copilot case fails with origin/main's pulls.py. Review C of #709, C1."
resolution: null
duplicate_of: null
---
Found by #709 review C (C1 and C2), https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6024842953. C1: _rest_actor (src/metabrowser/builtin_plugins/github/pulls.py) assumes REST names every app <GraphQL login>[bot]; the Copilot coding agent is GraphQL {__typename: Bot, login: copilot-swe-agent} and REST {login: Copilot, type: Bot} (reviewer's reads of makr-code/ThemisDB#8365 and t-h-omy/Volcanae#396), so a cold-opened Copilot pull request shows copilot-swe-agent[bot] until the first full read renames it Copilot. Fix: map the known exception beside _rest_actor with the evidence, and add it to test_an_app_authored_pull_reads_the_same_through_graphql_and_rest. C2: the plan's Phase 1 checklist says a stale record asks a window after the last ask; use the Page Changes section's words (after the last ask for a stale record).
