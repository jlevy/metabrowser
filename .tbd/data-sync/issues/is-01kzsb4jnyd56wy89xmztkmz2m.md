---
type: is
id: is-01kzsb4jnyd56wy89xmztkmz2m
title: "Repository library Phase 1B-a: hardened worktree-free Git acquisition (no serving)"
kind: task
status: in_progress
priority: 1
version: 39
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
hold: null
hold_until: null
created_at: 2026-08-11T21:19:58.653Z
updated_at: 2026-09-18T02:31:17.954Z
started_at: 2026-09-16T21:10:44.811Z
extensions:
  linear:
    id: 0ffb0ef8-e09f-4e96-8736-01e0592ab450
    linked_at: 2026-08-16T08:05:43.419Z
---
Extend the one Git runner with core-constructed trusted command targets, version detection, stdin isolation, non-interactive environment, and bounded acquisition/background policies. Acquire into an isolated worktree-free staging repository; record source, closed non-secret FetchAuthorizationContext kind, fetch-policy version, exact refspec, expected OID, object format, and base generation; validate before importing objects and CAS-publishing only Metabrowser-owned refs. Unknown SSH or credential-helper principals receive fresh unshareable contexts. Publish the validated immutable store first and the source alias as the sole visibility commit, with source-alias locking and crash reclamation for orphaned stores. Define deterministic provider-identity store derivation without a mutable provider-to-store pointer, but keep GitHub metadata, immutable tree serving, shared origins, checkouts, and indexes out of this bead.

## Notes

Implementation sliced. Slice A (Git runner): PR https://github.com/jlevy/metabrowser/pull/142 HEAD bc18c718 CI green. Slice B (file:// staging fetch, mb-kf4w): PR https://github.com/jlevy/metabrowser/pull/143 HEAD b29447a3 stacked on #142; all 7 CI checks green. Slice C (publish+reuse, mb-t7l7): PR https://github.com/jlevy/metabrowser/pull/144 HEAD 2387b6d0 stacked on #143; CI in flight. Distro-patched Git gate remains refuse. mb-cun0 is not a blocker to start implementation; evaluate it before mb-k900 serves acquired content. Remaining slices: prefetch+crash recovery, then mb-dg00 goldens + --no-serve (mb-1i98).
