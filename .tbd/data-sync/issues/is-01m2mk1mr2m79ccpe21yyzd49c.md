---
type: is
id: is-01m2mk1mr2m79ccpe21yyzd49c
title: "Phase 0C.2 review R10: validate capability evidence from the sdist"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T07:49:04.385Z
updated_at: 2026-09-16T07:49:10.359Z
---
The generic installed capability discovery and evidence smoke runs only against the wheel, while the sdist check now covers unrelated file suffixes and hygiene. Install the sdist in isolation or build the tested wheel from it and run the same provider, registry, corpus, and parser evidence checks. Add a negative test where sdist capability evidence or entry points are missing and require failure.
