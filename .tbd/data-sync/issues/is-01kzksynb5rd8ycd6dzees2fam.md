---
type: is
id: is-01kzksynb5rd8ycd6dzees2fam
title: "PR #22 review R1: provider prune allegedly drops global top matches (search_controller.js:238-252)"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01kzksyn1g7gqhyw86ssr1gfvt
created_at: 2026-08-09T17:43:26.820Z
updated_at: 2026-08-09T17:43:26.820Z
---
Bugbot 3732447656, Medium. Claim: intermediate prune to top-100 can omit better-ranked earlier files. Assessment: prune keeps top maxResults by the same total-order comparator as the final sort — streaming top-k, lossless. Candidate for rebuttal.
