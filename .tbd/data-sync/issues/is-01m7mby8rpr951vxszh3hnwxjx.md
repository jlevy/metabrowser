---
type: is
id: is-01m7mby8rpr951vxszh3hnwxjx
title: "#499 review A1 (High): land the mb-pc9v and mb-xorh fixes from main first, then merge main and get a green run, then merge #499 with #504"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7mby30w7w14nj5hhj6m9jx0
created_at: 2026-11-17T09:03:22.902Z
updated_at: 2026-11-17T09:03:53.981Z
---

## Notes

2026-11-17: disposition per the coordinator: adopt the ordering. The mb-pc9v and mb-xorh fixes land from main first (in their own PRs; the mb-pc9v fix is to explain why the job stopped after the worker was replaced), then main is merged into #499 with a green run at the new head (mb-g0xx's runs can serve), then #499 and #504 merge together as the stack. #499 does not merge main until the coordinator says the fixes have landed.
