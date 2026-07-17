---
type: is
id: is-01kxry268ht7t96d132pjadd8j
title: "Review C5: active_tracker full-inventory scan on loop + quiet_counters unbounded growth"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:05.265Z
updated_at: 2026-07-17T21:00:05.265Z
---
active_tracker.py:141 materializes up to 500K entries on the loop every 5s; quiet_counters never dropped for deleted files (active_tracker.py:179).
