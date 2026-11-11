---
type: is
id: is-01m75ky6cesq0d6q3d1rbcgpgc
title: "PR #348 G1: the console prompt estimate misses the pattern's optional parenthesis group"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m75ky4vdrf0qhqbhy15j46z4
created_at: 2026-11-11T15:34:32.589Z
updated_at: 2026-11-11T15:48:23.918Z
closed_at: 2026-11-11T15:48:23.916Z
close_reason: "Fixed in f959206b by removing highlighting from the revision page's render (kpress_adapter plain_code): no prompt pattern runs; review G's prompt shapes render in 3.5-3.8 ms. Test: test_fenced_code_renders_plain_whatever_language_it_names (fails without plain_code). CI 43049647459 green."
resolution: null
duplicate_of: null
---
Review G1 (https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5860828559): a 1,622-byte console line estimated 56.8 ms renders in 12.0 s.
