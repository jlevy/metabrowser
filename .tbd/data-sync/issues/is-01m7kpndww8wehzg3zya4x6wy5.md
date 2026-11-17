---
type: is
id: is-01m7kpndww8wehzg3zya4x6wy5
title: "Chrome flake: tests/test_github_pulls_stacks_chrome.py stalls at 'phase keys' (line 157), seen twice, once on main"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:33.147Z
updated_at: 2026-11-17T02:51:33.147Z
---
Found by the CI speed assessment (research-2026-11-16-ci-speed.md). Run 43987478737 attempt 1, test (3.13), on a pull request where another full-suite job passed on the same commit; and run 43981811898, test (3.13), on main. Both: test_the_pulls_stack_groups_share_the_stack_menus_design_in_chrome, AssertionError listing phases chrome 280, shell 1009, first row 1897, grouped 2074, keys 4232. Reproduce under load and fix the cause.
