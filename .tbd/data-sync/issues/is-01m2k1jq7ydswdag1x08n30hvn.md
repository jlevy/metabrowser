---
type: is
id: is-01m2k1jq7ydswdag1x08n30hvn
title: "Hosted review Phase 0C.1: compile enforced SoftSchema contracts in both runtimes"
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jrywxceb6n3r0pbadegx
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
child_order_hints:
  - is-01m2krx2resarv4h36yyeje2gj
  - is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-15T17:24:35.192Z
updated_at: 2026-09-16T03:29:16.660Z
---
Coordinate one formal Phase 0C.1 pull request stacked on the exact green Phase 0B.3 head after the reviewed first-party SoftSchema foundation is available. mb-52iz owns compiled enforced contracts, the packaged format inventory, and Python/JavaScript corpus parity; mb-vepa owns independent review, make verify, bead sync, gh publication, and final green CI. Close this phase only after both children are complete and its PR is registered with mb-n2ro.

## Notes

Pre-implementation architecture review from Phase 0B.3 identified two gates for 0C.1: (1) installed-plugin discovery currently requires manifest.toml plus index.js and has no backend-only trusted capability surface for artifact-contract/resource-profile declarations; decide and test a backend-only discovery path or make index.js conditional without a fake browser plugin or core hard-import; (2) neutral storage/repository contracts presently live under hosted_review although later mb-s0gv moves ownership to provider_resources, so registry identity must survive that move without persisted module paths, compatibility aliases, or core-to-domain coupling. Phase 0B.3 must also explicitly permit evidence-driven corrections and deliver a complete exact-provenance field/value-state oracle before contracts compile.
