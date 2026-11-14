---
type: is
id: is-01kxshfx0fhzyccg1wwtdv7c6b
title: Extend vendor pipeline with esbuild single-entry ESM bundling (workers, ESM-only libs)
kind: feature
status: open
priority: 3
version: 4
spec_path: TODO.md
labels:
  - build
dependencies: []
parent_id: is-01kxnx9vtb13p6z8mewgsm2t75
created_at: 2026-07-18T02:39:37.485Z
updated_at: 2026-11-14T18:43:14.988Z
extensions:
  linear:
    id: 66d2a207-9a94-44a8-afcb-f3a252eb2229
    linked_at: 2026-08-16T08:06:32.875Z
---
An option from docs/project/research/research-2026-07-18-browser-contributor-toolchain.md: a pinned bundler emits reviewed vendor artifacts. Add a bundling mode to devtools/vendor_assets.py that produces unminified single-file ESM artifacts for an ESM-only package, or for a worker whose dependency graph cannot use relative imports alone. Commit each artifact with a sha256 manifest and license, and add a CI rebuild-and-compare job. The research lists what a bundle must record: entry point and configuration, locked input graph and licenses, emitted files, hashes and size limits, the determinism expectation, and source maps.

Supply chain: esbuild 0.28.2 declares a postinstall script, so the review must prove a locked install and build with lifecycle scripts disabled.

No consumer today. The Markdown module worker (builtin_plugins/markdown/markdown-worker-client.js) runs without bundling, and an ESM-only renderer such as @pierre/diffs waits on mb-k0x3's decision. Raise vendor size caps only per artifact. The toolchain plan (mb-h31g) decides between this and a full toolchain.
