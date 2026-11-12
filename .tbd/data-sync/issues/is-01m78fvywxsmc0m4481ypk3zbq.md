---
type: is
id: is-01m78fvywxsmc0m4481ypk3zbq
title: "Environment sources: register environments, --plugins-env, listing cache, proxied hooks"
kind: task
status: open
priority: 1
version: 9
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
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:08.379Z
updated_at: 2026-11-12T18:47:17.115Z
---
Phase 1 (plan: Sources, The Registry, Process Model, Diagnostics). --plugins-add PATH for a venv, a uv project, a uv tool environment, or an interpreter, and the per-command --plugins-env PATH; the listing cache keyed by the environment fingerprint (interpreter identity, site-packages, *.dist-info, *.pth mtimes) in the cache home; manifests read by the host with its own schema and gate; /plugin-static/ served from each plugin directory; data hooks proxied to the environment's worker, started on evidence (first hook, parse, or classification into an owned kind); the content reader's host calls so hooks work on Git pins; --doctor's check op; --show names the owning source and process. Fixture plugin environment under tests/fixtures/plugin-env built offline with uv venv and a --no-index install; goldens for --plugins-env with --api and --show. Record spawn, listing, memory, and hook overhead with the spike's method and choose the idle exit from them.

## Notes

Review (2026-11-12, independent design review; plan updated to match): Identify environments by prefix (pyvenv.cfg directory), not interpreter: uv venv pythons symlink to the shared base interpreter. Fingerprint: pyvenv.cfg, base interpreter identity, site-packages, dist-info, .pth mtimes. A cold or stale listing runs before the classifier is built (251-469 ms measured), and CLI modes take it ahead of time. Write the listing cache only for registered sources or trusted repositories. A worker keeps the fingerprint the server started from; a changed environment reports 'restart to apply' until reload lands. Ownership rule before every spawn. Response bound set from measurement (64 MiB is the JSONL parser's input cap, not a response bound).
