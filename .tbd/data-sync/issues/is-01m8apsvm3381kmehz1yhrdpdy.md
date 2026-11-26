---
type: is
id: is-01m8apsvm3381kmehz1yhrdpdy
title: Stack page loaded on Guided Review reads step 1 only after the stack's answer
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-26T01:16:30.209Z
updated_at: 2026-11-26T01:16:30.209Z
---
From PR #859: a stack page opened directly on its Guided Review tab reads the guide's first step only after the stack's own answer arrives, so the guide's first paint waits on two sequential requests. Read the first step ahead alongside the stack (the guide's carrier is known from the stacks snapshot), within a measured budget.
