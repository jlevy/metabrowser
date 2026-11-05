---
type: is
id: is-01m6mzhaqwfp2frzwkpyjh7p62
title: "H80: attribute selected core to GraphQL viewer without a sixth gh process"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-prefetch-security
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T04:30:08.635Z
updated_at: 2026-11-05T04:30:30.412Z
started_at: 2026-11-05T04:30:30.412Z
---
Register before implementation: replace the fixed selected core REST read with a fixed GraphQL query carrying viewer.login and every existing validated PullRequest field, retain initial and final active-account checks and five REST discussion/check parts, and remove only the now-redundant preview-specific account subprocess after actual response viewer validation. Provider cost probe exp-048 observed selected PR294 complete validated-model equality across REST1/GraphQL1/GraphQL8/combined; GraphQL1 response 4660 bytes versus REST19764, while latency ranges overlap and prove no speed win. Existing candidate01 resource samples show six concurrent gh processes at all five RSS peaks versus five baseline. Hypothesis H80/exp-049: atomic-viewer core acquisition can restore at-most-five gh concurrency and lower cold family RSS/full-record delay without weakening observed-account, source, cancellation, cached-full or comparison behavior. Root owns source plan registration and serial acceptance. Prepare external architecture/patch only until cadence-only candidate02 acceptance; no batch implementation, compatibility branch or source change yet. Test malformed/mismatched viewer/repository/number, missing core, changed account, unknown mergeability, nullable actors/repositories, etags/304 contract, full-record refresh and head-retry revocation. Measure matched header/full phases/RSS and retain all failures before acceptance.
