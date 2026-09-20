---
type: is
id: is-01m2pn3sm2980e2bjnfd3b4xvp
title: "Untrusted-content profile review: publish HTML trust-chain PR"
kind: task
status: closed
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-17T03:03:40.930Z
updated_at: 2026-09-20T17:16:29.556Z
started_at: 2026-09-20T05:45:03.788Z
closed_at: 2026-09-20T17:16:29.554Z
close_reason: PR 209 independently reviewed on 2026-09-20 (first review it ever had), fixes f1b1c7e1 / 1c1eb1ad / ed08698d / 04534249 pushed through the full pre-push gate, CI green on all seven checks, validated by the user in a real browser against a hostile fixture, and merged to main as fd65812b with explicit user approval.
resolution: null
duplicate_of: null
---
Independently review the sandboxed /raw responses and same-origin /api proof (mb-cun0) plus the immutable capability set, --untrusted profile, and client publication (mb-vib1). Their implementation may proceed in parallel with the cache layers, but they publish as one formal stack layer directly before repository URL opening, because serving fetched content requires that gate. Resolve every finding, run make verify, and publish one formal GitHub PR with gh stacked on the exact green mb-hoae immutable Git-tree head. Its green head is the integration base mb-j439 records for Phase 2A. Record exact stack evidence and final green CI. Do not merge.

## Notes

HTML trust-chain implementation is draft #209 https://github.com/jlevy/metabrowser/pull/209 on main (not in stack #218).
Phases 1–4 are implemented on that branch. Publication/review of the trust gate before serving acquired Git remains this bead.
#209 includes a lock-only anyio 4.14.2 bump that overlaps dependabot #207.
Do not merge until asked. Do not restack onto #216 unless serving acquired Git is in scope.
