---
type: is
id: is-01m6jtxcrqybrpkrw91fnfp1sk
title: Report refused checkout file refreshes and back off without cache writes
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6jhbnan8czw6c97gr5511mr
hold: null
hold_until: null
created_at: 2026-11-04T08:30:52.182Z
updated_at: 2026-11-04T08:36:12.002Z
started_at: 2026-11-04T08:36:12.001Z
---
Independent real-cache probe confirmed an owning PR288 Medium: claim_source runs outside refresh_pull_files handled block, outer worker swallows PullDataError assuming a stamp exists, future-home refusal leaves GET absent/not_cached with last_refresh=null and automatic retry still due. Two actual attempts reproduce, zero gh and unchanged full home/config fingerprints. Handle claim failure in the worker and publish bounded in-memory cache_unwritable failure/backoff without locks, stamps or directories in refused cache; preserve shared rate-limit holds. Fix at paused clean PR288 checkpoint ca79c04d, independently review concrete negative/positive/no-write controls, then continue forward cascade. Existing normal final gate will cover this with file-generation and Markdown fixes.
