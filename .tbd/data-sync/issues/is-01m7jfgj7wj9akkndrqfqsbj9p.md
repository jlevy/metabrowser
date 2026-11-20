---
type: is
id: is-01m7jfgj7wj9akkndrqfqsbj9p
title: Test _drop_core_preview clearing repository_labels and labels_pending for a revoked core (#471 review C2)
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
created_at: 2026-11-16T15:27:19.291Z
updated_at: 2026-11-20T17:11:25.169Z
---
Review C on #471 (C2): removing the two clearing lines in sidekick.py _drop_core_preview leaves test_disk_core_revocation_after_worker_check_is_rejected_on_loop green, because its core's labels have colors. Add a direct test on two envelopes.
