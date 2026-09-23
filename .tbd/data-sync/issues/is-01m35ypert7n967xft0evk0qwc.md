---
type: is
id: is-01m35ypert7n967xft0evk0qwc
title: "Repository Phase 2B: bounded background object convergence after serving"
kind: feature
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2p38vk3d6gkv2ts21bzfzw3
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-23T01:39:46.073Z
updated_at: 2026-09-23T07:37:06.515Z
closed_at: 2026-09-23T07:37:06.514Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: none; git fetch writes objects before refs, gc is off, and gh owns credentials, so the job protocol, convergence and credential leases are retired."
resolution: null
duplicate_of: null
---
Implement the planned background convergence runtime after acquired-Git serving and the generic job/selected-ref foundation exist. Start only after serving begins; fetch remaining promised objects through the bounded explicit job path, preserve authorization/store identity and leases, report honest partial/converging/complete/failed outcomes, and support cancellation, interruption and restart without discarding usable cached content. Prove post-serving startup, completion, failure recovery and no implicit network on reads with focused runtime tests and goldens. Review with the Phase 2B publication mb-bf94. This work is not a blocker of Phase 1B-a acquisition implementation/publication mb-h51g/mb-k900; default-tree prefetch and initial object-state recording remain there. This task preserves existing planned scope while removing the accidental acceptance cycle exposed by the checkbox audit.
