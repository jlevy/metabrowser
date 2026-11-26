---
type: is
id: is-01m78fvywxsmc0m4481ypk3zbq
title: Per-command plugin environments (--plugin-env) and the --present refusal test
kind: task
status: in_progress
priority: 1
version: 18
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvzd8jj1kh0fpm00zt8zk
  - type: blocks
    target: is-01m78fvzzpbj5yemnpk3513vyz
  - type: blocks
    target: is-01m78fw0hdp37ztc29ebfzf2hp
  - type: blocks
    target: is-01m78fw226k1aejzey9xamd4e7
  - type: blocks
    target: is-01m78fw2nz4rpf95kybngf40zq
  - type: blocks
    target: is-01m78fw36avwntyj23v52vqqdm
  - type: blocks
    target: is-01m78fw3ppt7qjecxb1m4r276q
  - type: blocks
    target: is-01m78fvxxksc6ybfthkyzgbtdn
  - type: blocks
    target: is-01m8bfx0ydnsv7hpxbm60fxhzj
  - type: blocks
    target: is-01m8bfx0jk64cgj3sz7sm2nav4
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:08.379Z
updated_at: 2026-11-26T09:20:28.195Z
started_at: 2026-11-26T08:35:34.373Z
---
Phase 1 (plan: Sources and Scopes, The Registry's listing, CLI and Routes; Key Decision 5). One executable: metab --plugin-env PATH names a plugin environment for one command, identified by its pyvenv.cfg prefix, not its interpreter; the Python floor is read from pyvenv.cfg. No option that names a plugin source or records a decision is in --present's option set (_MODE_OPTIONS in cli/main.py), and a test fails if one is added; the first revision's second executable is dropped, since the documented sandbox exemption is the prefix metab --present. Here: the listing cache keyed by the environment fingerprint and written only for added or decided sources, a cold listing taken before the classifier is built, manifests read and assets served by the host, hooks proxied to the worker, the content reader's host calls, the ownership rule before each spawn and on the worker's sys.path, and --doctor's per-source checks. Acceptance: the motivating plugin's hooks, at the current SDK version, served from its own environment under a uv tool install, with no change to its Python beyond the runtime's import name. Fixture environment built offline, as explorations/plugin-worker-spike/probes.py builds one.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
