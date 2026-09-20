---
type: is
id: is-01m2zpxmwz32ykx0q3w62qhghh
title: "S139-1: specify the source rebind or tombstone path before Phase 3 storage"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr139
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:26.524Z
updated_at: 2026-09-20T17:47:03.271Z
closed_at: 2026-09-20T17:47:03.270Z
close_reason: "Rebind/tombstone path specified on stab/s139-rebind (81cd69d8): a typed rebind_required state, an explicit local-user trigger, the evidence required (fresh successor retrieval, previous-identity disposition, compare-and-swap naming both refs, same provider kind and instance), an append-only ProviderBindingRebind/v1 record with its own validator, what happens to cached bundles and leases, and a CLI inspection plus action route with goldens. Written into arch-hosted-review-model.md and as a Phase 3A checklist item; rides the #216 layer in the restack."
resolution: null
duplicate_of: null
---
Finding S139-1 from the v0.11 stabilization review. Owning layer: PR #139. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S139-1.
