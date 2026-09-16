---
type: is
id: is-01m2krvmvxvt6vhgq260mw7v8x
title: "Hosted review Phase 0B.2a: implement review, signal, and activity records"
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b2
dependencies:
  - type: blocks
    target: is-01m2krvwqaynstjykh0m9k90vr
parent_id: is-01m2k1jkq9cvxx9db7a0z14b0z
created_at: 2026-09-16T00:11:24.924Z
updated_at: 2026-09-16T03:12:53.534Z
closed_at: 2026-09-16T03:12:53.533Z
close_reason: Phase 0B.2 implementation, portable evidence, docs, delegated review fixes, and make verify are complete; publication is owned by mb-qpbu.
resolution: null
duplicate_of: null
---
Implement the complete no-network Phase 0B.2 record set in models.py, artifacts.py, the shared portable corpus, and focused tests: ChangeRequestComment, Review with optional Markdown summary, ReviewThread, ReviewComment, tagged file/line/range ReviewAnchor, Check, CommitStatus, and RepositoryActivity. Validate bounded relationships, immutable comparison/revision identities, unavailable or unresolved anchors, body/no-body reviews, unknown enums, and closed records without raw provider payloads or extension bags. Keep this implementation on one formal branch stacked on the green Phase 0B.1 PR.

## Notes

Implemented the complete Phase 0B.2 no-network contract layer on codex/v011-hosted-review-phase0b2: closed comment/review/thread/anchor/check/status/activity records; deterministic frontmatter codecs for prose-bearing artifacts; source-neutral Git/provider activity actors; independently sided range endpoints; nullable provider actors and review-less comments; observed unavailable review revisions; acyclic and scope-closed bundle relationships; truthful activity bounds; portable review/activity corpora; package exports; architecture/plan updates; and installed distribution smoke. Delegated implementation and two independent review rounds found and resolved all contract/evidence issues. Final focused evidence: 32 tests clean; repository make verify passed with 2212 tests, 124 golden scenarios, lint/type/parity/security/audits/distribution checks.
