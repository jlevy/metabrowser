---
type: is
id: is-01m6jhcsdtrmt1bb3ezcgqwff0
title: Audit all open PRs and preserve the excluded reference draft
kind: task
status: closed
priority: 1
version: 4
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6jhbnan8czw6c97gr5511mr
hold: null
hold_until: null
created_at: 2026-11-04T05:44:30.905Z
updated_at: 2026-11-04T13:48:45.060Z
started_at: 2026-11-04T13:48:40.084Z
closed_at: 2026-11-04T13:48:45.060Z
close_reason: The original feature-stack review, disposition, fix and publication scopes are complete. All21 requested feature PRs merged normally through native stacks278 and296, ending at main da87bb13c4434324af576b554711278139621b6b. Each owning fix and reviewed head is retained by ancestry; current-head CI and all exact publication/readback gates passed. The independently reproduced postlanding account-provenance bug remains open as mb-dvhc under mb-73n4, and the required documentation/skill/planning phase remains mb-ao35; this closure does not declare those later scopes complete.
resolution: null
duplicate_of: null
---
InventoryallopenPRs, confirm20featurePR heads/bases/ancestry/reviews/currentCI/conflicts, auditdraft247preservation-only branchlanding safety. Reference247remainsexcluded perexplicitdo-not-merge; do notsilentlyrestore retiredfeatures. ReconcileanyotheropenPRfound. Allrealconflictsresolved withforwardmerges onlybeforeauthorizedfeaturestacklanding.

## Notes

Inventoryexact21open:20featurestack+draft247only. All20heads/bases/ancestry/native2789/native28611match, mergeable/nondraft/noautomerge; original14allCIgreen. Independent247preservation-only landing audit confirms109filesrestore retiredentrypoints/SDK/cacheformats; old9CIchecksagainsthistoricalbase are notcurrent-mainE2E. Branch+datedtagpreserved, excludedfromlanding underexplicitdo-not-merge. Remainingfeaturemerge sequence awaitsnewQodofixes/tests/CI; no actualGitconflicts observed.
