---
type: is
id: is-01m6jtxcrqybrpkrw91fnfp1sk
title: Report refused checkout file refreshes and back off without cache writes
kind: bug
status: closed
priority: 1
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6jhbnan8czw6c97gr5511mr
hold: null
hold_until: null
created_at: 2026-11-04T08:30:52.182Z
updated_at: 2026-11-04T13:48:45.080Z
started_at: 2026-11-04T08:36:12.001Z
closed_at: 2026-11-04T13:48:45.080Z
close_reason: The original feature-stack review, disposition, fix and publication scopes are complete. All21 requested feature PRs merged normally through native stacks278 and296, ending at main da87bb13c4434324af576b554711278139621b6b. Each owning fix and reviewed head is retained by ancestry; current-head CI and all exact publication/readback gates passed. The independently reproduced postlanding account-provenance bug remains open as mb-dvhc under mb-73n4, and the required documentation/skill/planning phase remains mb-ao35; this closure does not declare those later scopes complete.
resolution: null
duplicate_of: null
---
Independent real-cache probe confirmed an owning PR288 Medium: claim_source runs outside refresh_pull_files handled block, outer worker swallows PullDataError assuming a stamp exists, future-home refusal leaves GET absent/not_cached with last_refresh=null and automatic retry still due. Two actual attempts reproduce, zero gh and unchanged full home/config fingerprints. Handle claim failure in the worker and publish bounded in-memory cache_unwritable failure/backoff without locks, stamps or directories in refused cache; preserve shared rate-limit holds. Fix at paused clean PR288 checkpoint ca79c04d, independently review concrete negative/positive/no-write controls, then continue forward cascade. Existing normal final gate will cover this with file-generation and Markdown fixes.
