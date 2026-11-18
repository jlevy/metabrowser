---
type: is
id: is-01m7nk0mpg970k2sgcheg6zfqw
title: "Clear npm audit: bump tryscript to the release that drops picomatch (GHSA-fc5q-39xc-vjpf)"
kind: chore
status: closed
priority: 1
version: 2
labels:
  - deps
  - security
dependencies: []
created_at: 2026-11-17T20:26:15.117Z
updated_at: 2026-11-17T21:04:00.961Z
closed_at: 2026-11-17T21:04:00.954Z
close_reason: "Duplicate of mb-p1o0 (opened alongside PR #523's exception); the tryscript 0.3.2 bump that removes the exception is tracked there"
resolution: null
duplicate_of: null
---
npm audit fails on GHSA-fc5q-39xc-vjpf (picomatch <=4.0.7 ReDoS, no patched release) via tryscript 0.3.1 -> tinyglobby -> picomatch, failing the lint gate on main and every PR. A new first-party tryscript release (0.3.2) removes picomatch; bump to it as a first-party exception to the release-age delay, documented in SUPPLY-CHAIN-SECURITY.md like 0.3.0 and 0.3.1, with the lockfile delta and artifact SHA-512.
