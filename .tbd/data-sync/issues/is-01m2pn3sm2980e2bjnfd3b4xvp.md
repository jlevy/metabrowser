---
type: is
id: is-01m2pn3sm2980e2bjnfd3b4xvp
title: "Untrusted-content profile review: publish HTML trust-chain PR"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-17T03:03:40.930Z
updated_at: 2026-09-17T03:03:54.248Z
---
Independently review the sandboxed /raw responses and same-origin /api proof (mb-cun0) plus the immutable capability set, --untrusted profile, and client publication (mb-vib1). Their implementation may proceed in parallel with the cache layers, but they publish as one formal stack layer directly before repository URL opening, because serving fetched content requires that gate. Resolve every finding, run make verify, and publish one formal GitHub PR with gh stacked on the exact green mb-hoae immutable Git-tree head. Its green head is the integration base mb-j439 records for Phase 2A. Record exact stack evidence and final green CI. Do not merge.
