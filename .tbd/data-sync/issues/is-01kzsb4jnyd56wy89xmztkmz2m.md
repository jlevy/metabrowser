---
type: is
id: is-01kzsb4jnyd56wy89xmztkmz2m
title: "Repository library Phase 1B-a: hardened worktree-free Git acquisition (no serving)"
kind: task
status: open
priority: 1
version: 27
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: null
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01m1389rewn2mkj8emj3wxwpr7
  - type: blocks
    target: is-01m2h3vkgbkeq82ch4mzkrch1g
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
  - type: blocks
    target: is-01m2p1pshr699c6pf8xqeer16j
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-11T21:19:58.653Z
updated_at: 2026-09-17T06:24:53.115Z
started_at: 2026-09-16T21:10:44.811Z
extensions:
  linear:
    id: 0ffb0ef8-e09f-4e96-8736-01e0592ab450
    linked_at: 2026-08-16T08:05:43.419Z
---
Extend the one Git runner with core-constructed trusted command targets, version detection, stdin isolation, non-interactive environment, and bounded acquisition/background policies. Acquire into an isolated worktree-free staging repository; record source, closed non-secret FetchAuthorizationContext kind, fetch-policy version, exact refspec, expected OID, object format, and base generation; validate before importing objects and CAS-publishing only Metabrowser-owned refs. Unknown SSH or credential-helper principals receive fresh unshareable contexts. Publish the validated immutable store first and the source alias as the sole visibility commit, with source-alias locking and crash reclamation for orphaned stores. Define deterministic provider-identity store derivation without a mutable provider-to-store pointer, but keep GitHub metadata, immutable tree serving, shared origins, checkouts, and indexes out of this bead.

## Notes

From mb-ire2 review (decision recorded, not made): distributions backport Git CVE fixes without changing the upstream version string (Ubuntu 24.04 patched Git reports 2.43.0; Debian 12 reports 2.39.x), so an upstream-version acquisition gate refuses those builds. Decide before shipping acquisition among: refuse with an actionable message naming the upstream floor; a user-set acknowledgement setting; or a distro-package check. Also: run the no-lazy-fetch read tests against the lowest admitted Git in CI, and measure a low-speed stall bound on a large or bitmap-less initial acquisition before bounding it.
