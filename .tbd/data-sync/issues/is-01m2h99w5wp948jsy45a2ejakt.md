---
type: is
id: is-01m2h99w5wp948jsy45a2ejakt
title: "PR #125 review C-R1: add non-secret authorization context identity"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:01:05.081Z
updated_at: 2026-09-15T01:38:07.191Z
closed_at: 2026-09-15T01:38:07.190Z
close_reason: "Fixed C-R1/A-R7: AuthorizationContextRef is stable namespace identity only; volatile login/scopes/time live in Retrieval/v1, only stable fields are hashed, and unresolved authenticated identity refuses publication. Added exact tests to mb-i3xc and bounded /user resolution to mb-p4sw."
resolution: null
duplicate_of: null
---
PR #125 contracts C-R1/A-R7. Define AuthorizationContextRef as stable non-secret namespace identity only: provider instance, anonymous/authenticated mode, stable opaque principal ID for authenticated publication, and an optional normalized capability-partition fingerprint only when it changes object visibility. Put display login, observed scopes/capabilities, and observation time in Retrieval/v1, outside the key. Digest only the stable projection; refuse authenticated publication when no stable principal can be resolved; bind validators, outcomes, current, and last-complete to that key. Test repeated observations, capability partition changes, reauthentication, explicit cross-context offline fallback, and reclamation; never persist tokens or credential-store paths.
