---
type: is
id: is-01m7jeqn2vkqqx0cxf0xv213mc
title: "PR #452 A3: six new claims disagree with the code (origin commands, history cursor, _run_cli, --api on SSE, repository_store premise, Server-Timing)"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpct6qpjeqfpyetf79fef
hold: null
hold_until: null
created_at: 2026-11-16T15:13:43.002Z
updated_at: 2026-11-16T15:27:46.440Z
started_at: 2026-11-16T15:14:15.061Z
closed_at: 2026-11-16T15:27:46.437Z
close_reason: "Fixed in c0a790e5a: (a) names pull_refs.py's third origin fetch; (b) adds d and attributes the page-size check to HistorySessionRegistry.read_page; (c) names cli/main.py; (d) --api refuses SSE at the headers (verified: exits with the SSE error in ~3.6 s wall incl. startup); (e) premise scoped to a full store; (f) every non-streaming route."
resolution: null
duplicate_of: null
---
Low. arch-mirror-acquisition-and-refresh.md:36-37; arch-git.md:211-215; arch-cli.md:45-50; skills/metabrowser/SKILL.md:113-114; cache/repository_store.py:7-12; devtools/bench_serving.py:31-32. Review A on PR #452: https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5922214786
