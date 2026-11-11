---
type: is
id: is-01m75ky7n9fdvr0j4nc77herck
title: "PR #348 G4: the console charge reads private Pygments attributes with an untested fallback"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m75ky4vdrf0qhqbhy15j46z4
created_at: 2026-11-11T15:34:33.897Z
updated_at: 2026-11-11T15:48:24.955Z
closed_at: 2026-11-11T15:48:24.954Z
close_reason: "Fixed in f959206b: no Pygments import or private attribute read remains in pull_snapshot.py; the console model and its fallback are deleted. KPress's fence highlighter is wrapped once in kpress_adapter behind a context variable; test_plain_code_shows_fences_escaped_and_leaves_other_renders_highlighted pins the cache separation."
resolution: null
duplicate_of: null
---
Review G4 (https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5860828559): private attributes, an unsafe fallback, Pygments undeclared, found.group(2) can raise.
