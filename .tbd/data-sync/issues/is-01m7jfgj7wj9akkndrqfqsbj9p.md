---
type: is
id: is-01m7jfgj7wj9akkndrqfqsbj9p
title: Test _drop_core_preview clearing repository_labels and labels_pending for a revoked core (#471 review C2)
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T15:27:19.291Z
updated_at: 2026-11-16T15:27:19.291Z
---
Review C on #471 (C2): removing the two clearing lines in sidekick.py _drop_core_preview leaves test_disk_core_revocation_after_worker_check_is_rejected_on_loop green, because its core's labels have colors. Add a direct test on two envelopes.
