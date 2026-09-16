---
type: is
id: is-01m2mk1mdfdj5eq8znnr2gk0bp
title: "Phase 0C.2 review R9: reject Node-only browser parser modules"
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T07:49:04.046Z
updated_at: 2026-09-16T08:01:53.100Z
---
The browser evidence harness imports declarations in unrestricted Node, so a module using node built-ins or process can pass even though it cannot load in a browser. Evaluate exact parser bytes in a browser-equivalent restricted ESM context or first enforce self-contained no-import/no-Node-global rules, then add negative tests for node:fs and process while retaining exact-byte execution and completion proof.

## Notes

Implemented exact-byte browser-parser execution with vm.SourceTextModule in a restricted browser-like context. Imports, including node:fs, are rejected; Node-only globals such as process and Buffer are absent; declared exports and every selected corpus case still execute, while the successful subprocess completion-proof handshake remains independently tested. Public plugin docs, durable plan, and changelog define the portability boundary. Integrated focused suite: 103 passed; Ruff, BasedPyright, Biome, Flowmark, and installed artifact inventory gate pass. Leave in_progress until PR disposition.
