---
type: is
id: is-01kxj67pctmr4k4mdmvd45cnq5
title: Support transparent bounded Zstandard artifacts
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-15T06:08:13.209Z
updated_at: 2026-07-15T06:16:17.432Z
---
Add .zst single-file compression to the same transparent ArtifactPath contract as .gz and .zlib: preserve logical extension/name, enforce compressed-input/decompressed-output/CPU bounds, classify and render the decoded file, cover raw/preview/structured/JSONL/KPress/tree/UI behavior, and audit any new dependency under repository supply-chain policy.

## Notes

Audited and confirmed .zst was never transparently implemented in the prior trading MetaBrowser or current standalone repository. User explicitly deferred implementation to TODO. Future dependency candidate is zstandard>=0.25.0, but no dependency or code was added; this is not a v0.1.0 merge blocker.
