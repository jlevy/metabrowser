---
type: is
id: is-01m7pr9wr8d30pckgvp4teba1z
title: "Recent targets: time a serve's start with recording on, and leave the module unimported under the opt-out"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-18T07:17:55.591Z
updated_at: 2026-11-18T07:17:55.591Z
---
Review A17 on #546 (mb-40k4). Every benchmark harness sets METABROWSER_RECORD_RECENT=0, so the record a user's serve makes is in no measurement: the reviewer measured 4.5 ms to import metabrowser.recent_targets and 1.6 to 3.0 ms per record at load average 14. #546 stopped resolving the root under the opt-out but still imports the module in serve_until_interrupted. Do: one startup pair (explorations/performance-loop/startup_pairs.py) with recording on and a scratch configuration directory, recorded beside LOCK_WAIT_S in recent_targets.py; and check RECORD_ENV before the import. Deferred from #546: a measurement on a quiet machine, which the shared one was not.
