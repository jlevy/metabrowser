---
type: is
id: is-01kxj67pctmr4k4mdmvd45cnq5
title: Support transparent bounded Zstandard artifacts
kind: feature
status: open
priority: 2
version: 3
spec_path: TODO.md
labels: []
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-15T06:08:13.209Z
updated_at: 2026-07-17T20:20:44.602Z
---
Add .zst single-file compression to the same transparent ArtifactPath contract as .gz and .zlib: preserve logical extension/name, enforce compressed-input/decompressed-output/CPU bounds, classify and render the decoded file, cover raw/preview/structured/JSONL/KPress/tree/UI behavior, and audit any new dependency under repository supply-chain policy.

## Notes

Audited and confirmed .zst was never transparently implemented in the prior trading MetaBrowser or current standalone repository. User explicitly deferred implementation to TODO. Future dependency candidate is zstandard>=0.25.0, but no dependency or code was added; this is not a v0.1.0 merge blocker.
