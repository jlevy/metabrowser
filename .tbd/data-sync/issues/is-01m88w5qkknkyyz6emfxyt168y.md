---
type: is
id: is-01m88w5qkknkyyz6emfxyt168y
title: guided_review's deferred import of pull_rendered_diff has no boundary test
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
labels: []
dependencies: []
parent_id: is-01m8806zrnxn9jwj89hffd2yv7
created_at: 2026-11-25T08:11:53.326Z
updated_at: 2026-11-25T08:11:53.326Z
---
guided_review.py _step_references imports rendered_format from pull_rendered_diff inside the function so the description's render (pull_markdown imports guided_review for guide_introduction) does not load the projections. Measured 2026-11-25: importing pull_rendered_diff after pull_markdown took 164-364 ms (3 runs, load ~212 on 10 cores). docs/development.md 'Deferred Imports' requires each kind to have a test holding its boundary; this one has none and is not listed. Either add it to the list with a fresh-interpreter test that importing pull_markdown does not load pull_rendered_diff, or move the import to the top. Raised as an aside in PR #822 review A6 (https://github.com/jlevy/metabrowser/pull/822#pullrequestreview-6053614872); the import itself came from #806.
