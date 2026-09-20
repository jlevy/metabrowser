---
type: is
id: is-01m2zpx351fryc2z9hjb2m4j4a
title: "S209-1: a cloned repo's .env can override --untrusted through the dotenv chain"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr209
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:08.350Z
updated_at: 2026-09-20T16:48:13.051Z
closed_at: 2026-09-20T16:48:13.045Z
close_reason: "Fixed in f1b1c7e1 on stab/s209 (pending push to PR 209): explicit --untrusted beats environment enables, and the dotenv loader never contributes capability variables or METABROWSER_ALLOWED_HOSTS. Five regression tests, red before and green after; end-to-end check with the real console script."
resolution: null
duplicate_of: null
---
Finding S209-1 from the v0.11 stabilization review. Owning layer: PR #209. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S209-1.
