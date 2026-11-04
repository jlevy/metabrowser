---
type: is
id: is-01m6jrdfayb71zm3ck9p929cys
title: Keep delayed PR Markdown rendering bound to its current record
kind: bug
status: closed
priority: 1
version: 4
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6jhbnan8czw6c97gr5511mr
hold: null
hold_until: null
created_at: 2026-11-04T07:47:13.373Z
updated_at: 2026-11-04T13:48:45.070Z
started_at: 2026-11-04T07:49:09.513Z
closed_at: 2026-11-04T13:48:45.070Z
close_reason: The original feature-stack review, disposition, fix and publication scopes are complete. All21 requested feature PRs merged normally through native stacks278 and296, ending at main da87bb13c4434324af576b554711278139621b6b. Each owning fix and reviewed head is retained by ancestry; current-head CI and all exact publication/readback gates passed. The independently reproduced postlanding account-provenance bug remains open as mb-dvhc under mb-73n4, and the required documentation/skill/planning phase remains mb-ao35; this closure does not declare those later scopes complete.
resolution: null
duplicate_of: null
---
The dedicated correctness review at a7b964c4 reproduced stale Markdown publication: a record A HTML response passes the controller check, waits for inert/style assets, then renderMarkdown looks up the current texts map after record B replaces it and inserts old A HTML into B. This structure already exists on main c934; the newer CSS await also exposes the boundary. Add a focused new stacked PR with a post-await record, element and disposal ownership guard, meaningful delayed-asset negative/positive controls, independent review, normal gates/CI and affected whole-shell acceptance. Preserve plain current text when obsolete work finishes. No source mutation while the existing normal push hook runs.

## Notes

The baseline Markdown scope now includes two confirmed Medium races. First, an accepted A render can wait for inert/style assets and then write into B's current text element. Second, same-second changed records can reuse either an in-flight A response or cached A HTML because the controller keys ownership by fetched_at alone. The server render key already includes raw text; browser/server record attribution is missing. Nav prepares a coherent explicit record-revision contract plus element/disposal post-await guard outside source, reviewed independently by the security reviewer. Keep timestamps for display/freshness, preserve same-record positive controls, and avoid per-warm-GET full-record hashing or racy independent file-stat tokens. New focused stacked layer atop the completed owning287 forward fix; no source changes while push41771 runs.
