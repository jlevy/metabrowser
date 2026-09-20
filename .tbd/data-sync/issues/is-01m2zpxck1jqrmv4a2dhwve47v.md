---
type: is
id: is-01m2zpxck1jqrmv4a2dhwve47v
title: "S134-1: decide Hosted Review format hardening before freeze: object id regex, canonical bytes, length bounds, id ambiguity, timestamp ordering"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr134
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:18.012Z
updated_at: 2026-09-20T17:46:57.769Z
closed_at: 2026-09-20T17:46:57.766Z
close_reason: "Six hardening items ported to the #139 layer on stab/s139-hardening (exact 40/64 hex oid, canonical artifact bytes plus strict strings, bounded strings and refused hidden characters, ChangeRequest.id verified against structured fields, provider-supplied timestamps no longer ordered, URL allowlist ends at path boundaries). Python, the JS mirror, six corpora and sixteen compiled schemas all agree; each item proven by reverting and watching the corpus fail; 268 focused tests pass and make lint-check is clean. Landed at #139 rather than #134 because re-mirroring through two layers would have doubled the JS/corpus/schema work; no higher layer touches these files. Residuals filed separately."
resolution: null
duplicate_of: null
---
Finding S134-1 from the v0.11 stabilization review. Owning layer: PR #134. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S134-1.
