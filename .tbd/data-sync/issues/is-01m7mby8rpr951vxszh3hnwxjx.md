---
type: is
id: is-01m7mby8rpr951vxszh3hnwxjx
title: "#499 review A1 (High): land the mb-pc9v and mb-xorh fixes from main first, then merge main and get a green run, then merge #499 with #504"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m7mby30w7w14nj5hhj6m9jx0
created_at: 2026-11-17T09:03:22.902Z
updated_at: 2026-11-18T02:28:25.803Z
closed_at: 2026-11-18T02:28:25.803Z
close_reason: "Fast CI stack #499+#504 merged to main at d46d0359a on 2026-11-17, after #513/#514/#515 landed first (review A1's ordering); reviews A-C addressed; owner approved the AGENTS.md merge procedure in chat."
resolution: null
duplicate_of: null
---

## Notes

2026-11-17: disposition per the coordinator: adopt the ordering. The mb-pc9v and mb-xorh fixes land from main first (in their own PRs; the mb-pc9v fix is to explain why the job stopped after the worker was replaced), then main is merged into #499 with a green run at the new head (mb-g0xx's runs can serve), then #499 and #504 merge together as the stack. #499 does not merge main until the coordinator says the fixes have landed.
