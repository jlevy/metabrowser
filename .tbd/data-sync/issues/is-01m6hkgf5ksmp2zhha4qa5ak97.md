---
type: is
id: is-01m6hkgf5ksmp2zhha4qa5ak97
title: Audit PR request payload sizes and review lazy detail and Git diff fetching
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:02:14.194Z
updated_at: 2026-11-03T21:14:22.229Z
started_at: 2026-11-03T21:05:42.366Z
---

## Notes

Read-only payload audit at ea771741 completed: four matching100-row public REST/GraphQL pairs showed39.68–47.07x smaller decoded catalogpayload(1.90–2.21MB vs46–49KB), withcurrentrowfields+exactall/open/closedcounts. Singlelatenciesoverlap; no general latencyclaim. PublicPR288filesREST378998B includes331757B discardedpatch; minimalGraphQL5605B lacks previousfilename. Coordinator declinedhybrid to preserveprogressive listing/rename semantics; mb-0cr3 staysopenfollowup, no productchanges. Exact productionAPI-stage cold6requests347257B1.534s; warm6conditionalrequests all304/0B1.463s, recordfit+serialize~3.9ms. No mainpipeline rewrite justified. Durable evidence catalog-payload-ea771741/{design-audit.json,metrics.json,supplement.json,detail-conditional.json,threeprobes}. Now independently reviewingin-progress catalogdesign; formalreview awaitssettledimmutablepin.
