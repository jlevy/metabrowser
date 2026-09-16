---
type: is
id: is-01m2h7h50h2y8hhhq7x7f1zcmd
title: "GitHub Phase 3B: directly addressed PR bundle and selected refs"
kind: feature
status: open
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7hrjfx06hzpr7ptz7k9wn
  - type: blocks
    target: is-01m2h7hrjt6yzb16neh8g2zvsd
  - type: blocks
    target: is-01m2kw2c5sak3agfksaqecefa5
parent_id: is-01m2h3vtmk6apasv27t6ygrrxf
hold: null
hold_until: null
created_at: 2026-09-15T00:30:06.351Z
updated_at: 2026-09-16T22:39:02.169Z
started_at: 2026-09-16T21:10:44.896Z
---
Hydrate one directly addressed PR without requiring an index or managed checkout. Publish the enforced ChangeRequest bundle and bounded comments, reviews, threads, checks, statuses, retrievals, and manifests into the shared repository/auth-scoped provider mirror. Ask mb-jlon to fetch only selected base, head, and optional merge OIDs into the shared store when content is requested. Name the actual provider-declared credential-free HTTPS source for every object, including forks, and pass the opaque GitFetchCredentialLease from the same pinned provider session that observed the full OIDs. Verify objects against that observation and keep local availability separate. Prove GH_TOKEN-only private-style acquisition with ambient Git auth disabled, reuse across URL sources and attached clones, no ambient-principal fallback, external gh auth switch isolation, lease expiry/revocation/broker-loss/cancellation behavior, fork sources, secret-free diagnostics, partial and not-found states, last-complete fallback, and offline inspection.
