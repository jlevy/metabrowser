---
type: is
id: is-01kzsb4jnyd56wy89xmztkmz2m
title: "Repository library Phase 1B-a: hardened worktree-free Git acquisition (no serving)"
kind: task
status: in_progress
priority: 1
version: 57
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
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
child_order_hints:
  - is-01m2s27ybx4dw3qde29xm6jgqn
  - is-01m2s4vpjy6j5rysn5x8ah2e03
  - is-01m2s5c9jf071q4nbn7v8vxwxe
  - is-01m2s5wzeb3y0zb5qx03bkmp03
  - is-01m2s7nv8hmezt4nt3z64qbvpp
  - is-01m2s8cm123a90x0ffhp6t9jrc
  - is-01m2s8yd0j4rksp89yhdktxjzr
  - is-01m2s9k0ratabccfcr0ncj0ac6
  - is-01m2sabkcgvvt9h1qdkgqb24w5
hold: null
hold_until: null
created_at: 2026-08-11T21:19:58.653Z
updated_at: 2026-09-18T18:32:39.309Z
started_at: 2026-09-16T21:10:44.811Z
extensions:
  linear:
    id: 0ffb0ef8-e09f-4e96-8736-01e0592ab450
    linked_at: 2026-08-16T08:05:43.419Z
---
Extend the one Git runner with core-constructed trusted command targets, version detection, stdin isolation, non-interactive environment, and bounded acquisition/background policies. Acquire into an isolated worktree-free staging repository; record source, closed non-secret FetchAuthorizationContext kind, fetch-policy version, exact refspec, expected OID, object format, and base generation; validate before importing objects and CAS-publishing only Metabrowser-owned refs. Unknown SSH or credential-helper principals receive fresh unshareable contexts. Publish the validated immutable store first and the source alias as the sole visibility commit, with source-alias locking and crash reclamation for orphaned stores. Define deterministic provider-identity store derivation without a mutable provider-to-store pointer, but keep GitHub metadata, immutable tree serving, shared origins, checkouts, and indexes out of this bead.

## Notes

Cache 1B-a #141–#151 measured as 11 small layers (711/491/460/526/178/503/521/95/297/261/151). Combined vs #140: 31 files, +3721/−309.

Grouped into 2 phase branches at existing tip SHAs (no new commits):
1. cursor/v011-cache-acquire-path-bd04 @ f369c4cf — #141–#145 grammar+runner+stage+publish+prefetch, 14 files +2066/−260, base #140
2. cursor/v011-cache-cli-hygiene-bd04 @ dc4223a0 — #146–#151 --no-serve+goldens+floor+reclaim+readonly hit+last_opened, 26 files +1696/−90, base phase 1

gh write failed (Resource not accessible by integration). ManagePullRequest missing in this session. Draft PRs not opened; #141–#151 not closed. Do not merge. Live tryscripts still wait on mb-oueh. Do not start mb-ew38.
