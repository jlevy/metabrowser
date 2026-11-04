---
type: is
id: is-01m6kb7a7528d1apcy8p2s87wf
title: Keep the local PR shortcut consistent about explicit stack requests
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:15:54.468Z
updated_at: 2026-11-04T13:15:54.468Z
---
Documentation review D17: human-maintained local create-or-update-pr-simple fork says an explicit stack request may use flat paths because no standing stack grant exists, contradicting its own authorization step and the validation-plan sibling. Match the sibling's condition for when nobody requested a stack. Preserve generated baselines, .tbd/doc-forks/base, .tbd/config and all recorded grants; this is a narrow contradictory-prose correction, not a policy or tool setup change.
