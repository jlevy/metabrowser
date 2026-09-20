---
type: is
id: is-01kzcvmqfy6gw5h36vs1hx3bms
title: "HTML P2: capability set, --untrusted profile, and client publication"
kind: task
status: closed
priority: 1
version: 17
spec_path: docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzcvmr0d1eyegyds8zpbffbz
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01m10vgwqwn8gjdv8fm183vztr
  - type: blocks
    target: is-01m2h7hrjt6yzb16neh8g2zvsd
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
  - type: blocks
    target: is-01m2pn3sm2980e2bjnfd3b4xvp
parent_id: is-01kzcvm6cpe5b8sb9b9n3gb16g
hold: null
hold_until: null
created_at: 2026-08-07T00:58:17.469Z
updated_at: 2026-09-20T05:50:32.685Z
started_at: 2026-09-18T04:14:57.485Z
closed_at: 2026-09-20T05:50:32.685Z
close_reason: "Implemented on survivor draft #209 https://github.com/jlevy/metabrowser/pull/209 (parallel to stack #218). Publication review remains mb-d658. Nothing merged to main."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 799c6e7a-191e-4d81-86b5-0a581e9e54c1
    linked_at: 2026-08-16T08:05:43.354Z
---
Resolve an immutable capability object before app construction. Add --no-active-content / METAB_ACTIVE_CONTENT=0 and the --untrusted / METAB_UNTRUSTED=1 profile, with individual flags overriding the profile. Publish through client_settings_dict() as CAPABILITIES and via GET /api/capabilities. When active_content is off, drop allow-scripts from the raw sandbox directive (NOT a text/plain downgrade — that reintroduces the type enumeration the unconditional header removed and breaks innocent styled pages). Document the flags in SECURITY.md and the README warning block in the same change. Generalizes the mechanism the file-actions plan defines for mutations rather than adding a parallel one.

## Notes

HTML #152–#155 measured 393/560/176/1037. Combined vs main: 43 files, +1993/−125 (<~4k), so one parallel phase on main — not mixed into cache/git.

Branch pushed at existing tip SHA (no new commit): cursor/v011-html-trust-preview-bd04 @ 6a0fe8a8, base main, supersedes #152–#155 (sandbox /raw + same-origin /api, --untrusted, path-shaped /raw, html kind + preview).

gh write failed (Resource not accessible by integration). ManagePullRequest missing in this session. Draft PR not opened; #152–#155 not closed. Bead stays open for review; do not merge. Do not start mb-d658.
