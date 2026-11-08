---
type: is
id: is-01m6wdjwawp9g1bvnefz2hxze3
title: Prepare the next Metabrowser release candidate without publishing
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6sx9vy43qz7syctdkmhf455
created_at: 2026-11-08T01:50:20.508Z
updated_at: 2026-11-08T01:50:20.508Z
---
After the reviewed native stack302 merges, follow docs/publishing.md: verify clean exact main, full make verify and exact-head CI; choose the semantic version from actual changes and current published release; run the standard previous-release performance loop with installed wheel artifacts, unchanged project-10 corpus, at least three cold headed browser samples and backend comparisons per condition; record all correctness, responsiveness and semantic-equivalence verdicts, regenerate the performance report, refresh changelog/release notes/current documentation and portable skill, and prepare the final approval checklist. Preserve failed or inconclusive evidence. Do not create a version tag, publish a GitHub release or dispatch PyPI publication until the user approves. Post-publication metadata/install/skill verification must remain clearly deferred until approval and publication.
