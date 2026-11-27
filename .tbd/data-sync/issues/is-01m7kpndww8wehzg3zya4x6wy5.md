---
type: is
id: is-01m7kpndww8wehzg3zya4x6wy5
title: "Chrome flake: tests/test_github_pulls_stacks_chrome.py stalls at 'phase keys' (line 157), seen twice, once on main"
kind: bug
status: in_progress
priority: 2
version: 9
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/913
    at: 2026-11-27T10:13:18.821Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/894
    at: 2026-11-27T11:02:54.163Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
hold: null
hold_until: null
created_at: 2026-11-17T02:51:33.147Z
updated_at: 2026-11-27T11:02:54.164Z
started_at: 2026-11-27T10:03:23.659Z
---
Found by the CI speed assessment (research-2026-11-16-ci-speed.md). Run 43987478737 attempt 1, test (3.13), on a pull request where another full-suite job passed on the same commit; and run 43981811898, test (3.13), on main. Both: test_the_pulls_stack_groups_share_the_stack_menus_design_in_chrome, AssertionError listing phases chrome 280, shell 1009, first row 1897, grouped 2074, keys 4232. Reproduce under load and fix the cause.

## Notes

2026-11-17: the same test failed again with another symptom, in chrome (3.13, 3/4) of run 44037230262 (jlevy/metabrowser#504, the first run of the split workflow): phases chrome 255, shell 967, then 'timed out waiting for document.querySelector(".github-pulls-item") !== null' with the list reading 'The repository could not be recorded in the cache.' while the stacks route answered current. The test is the only one in its module, so it is not a shard-order dependence. Not rerun; the run was superseded.

2026-11-26: performance stack PR 894 at be2228392, run 45915613821 Chrome 3.12 shard 3/4, job 140234062528. The third keyboard step focused #105 while #106 was transiently absent (its aria-expanded read was null rather than false). All 21 other shard tests passed. On local arm64 under high load, the same exact branch once failed earlier when #10 moved from stack 286 to 300. The matched upstream 71dded6d test passed once. Requested one retry of the failed hosted shard. The PR changes only the image preview at runtime; no Pulls keyboard or grouping change.

2026-11-27: main 63a00c89, CI 45976882655, Chrome 3.14t shard 3/4 job 140430833587. All 23 other tests passed. The known Pulls stack fixture had its earlier alternate-membership symptom: PR 10 moved to stack 300, with stack 286 still showing 4 members and menu [10, 9, 8, 7]. One targeted retry requested under AGENTS main CI gate.

2026-11-27: former #907 stack-integration Chrome run 45977287785, job 140432248617, hit the other symptom logged on #894. ArrowDown focused #105, and the independently sampled #106 accordion was temporarily outside the rendered window. The following read found #106 again. Main 63a00c89 retry passed. Checking a same-frame keyboard observation and waiting for target membership in the rendered stack before the final projection.
