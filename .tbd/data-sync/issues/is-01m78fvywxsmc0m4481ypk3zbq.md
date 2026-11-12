---
type: is
id: is-01m78fvywxsmc0m4481ypk3zbq
title: Per-command environment sources and the metab-plugins executable
kind: task
status: open
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
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
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:08.379Z
updated_at: 2026-11-12T21:18:02.588Z
---
Phase 1 (plan: Sources and Scopes, The Registry's listing, CLI and Routes; Key Decision 5). A second console script, metab-plugins: the same command line as metab that also accepts the flags that run plugin code without a recorded decision or record one; metab refuses them and names metab-plugins. Here: --env PATH for one command (an environment identified by its pyvenv.cfg prefix, not its interpreter), the listing cache keyed by the environment fingerprint and written only for added or decided sources, a cold listing taken before the classifier is built, manifests read and assets served by the host, hooks proxied to the worker, the content reader's host calls, the ownership rule (ExecutableTrust) before each spawn, and --doctor's per-source checks including the Python 3.12 floor. Acceptance: the motivating plugin's hooks served from its own environment under a uv tool install with no change to the plugin. Fixture environment under tests/fixtures/plugin-env built offline.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
