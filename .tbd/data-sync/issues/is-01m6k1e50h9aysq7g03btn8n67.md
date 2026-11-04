---
type: is
id: is-01m6k1e50h9aysq7g03btn8n67
title: Preserve the latest file-list outcome alongside the strongest provider hold
kind: bug
status: closed
priority: 2
version: 5
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6jhbnan8czw6c97gr5511mr
hold: null
hold_until: null
created_at: 2026-11-04T10:24:52.751Z
updated_at: 2026-11-04T13:48:45.085Z
started_at: 2026-11-04T10:32:11.978Z
closed_at: 2026-11-04T13:48:45.085Z
close_reason: The original feature-stack review, disposition, fix and publication scopes are complete. All21 requested feature PRs merged normally through native stacks278 and296, ending at main da87bb13c4434324af576b554711278139621b6b. Each owning fix and reviewed head is retained by ancestry; current-head CI and all exact publication/readback gates passed. The independently reproduced postlanding account-provenance bug remains open as mb-dvhc under mb-73n4, and the required documentation/skill/planning phase remains mb-ao35; this closure does not declare those later scopes complete.
resolution: null
duplicate_of: null
---
New postpush PR288 review comment discussion_r4466332226 questions read_files_refresh choosing the entire strongest-deadline stamp and potentially hiding a newer memory cache_unwritable outcome. Ordinary older durable hold is already copied into the memory refusal; verify the concurrent later-publication case through real worker/route behavior before accepting or rebutting. Preserve strongest live provider reset and automatic retry behavior. Independent read-only adjudication assigned; source0487921d remains frozen. Public finding: https://github.com/jlevy/metabrowser/pull/288#discussion_r4466332226. Keep landing gated on a concrete disposition.

## Notes

Confirmed Medium on exact 0487921d through two real worker processes. An admitted worker captures an older provider-rate outcome, pauses before durable publication, and later hides a newer in-memory cache refusal. Automatic retries remain held; this is an outcome-observability defect. The ordinary already-visible disk hold is copied into the refusal and does not fail. Evidence: qodo-288-outcome-adjudication-048/probe-red.json.

Fixed forward in owning PR288 commit 8853ccf0; source selects the newest outcome independently from the strongest active provider reset. Existing active equal-time precedence and expired/no-hold memory precedence remain. Two concise regressions use the real private writer and public envelope. The unchanged two-process probe fails before and passes after; author nine focused cases and independent three focused cases pass. Root's 75 file-list/checkout tests pass. The normal hook reformatted two expressions only; independent whole-file AST reconciliation confirms no semantic change.

All seven dependent branches were merged forward without conflicts; final local top a4e9db6a, with exactly one production function and one test file changed versus 048. All seven owned upper-layer patches are unchanged, every prior/base commit remains an ancestor, and both WIP refs are preserved. Receipts: p44c-forward-8853ccf0/CASCADE.json and p44c-independent-security-correctness-048/forward-composition-a4e9db6a.json.

The exact 1136+a4e9 wheel matches all 341 source files; fresh eight public-live tests passed. Full make verify, installed regression/native checks and focused browser acceptance are running. The prior published 048 map passed 21 heads/27 CI runs/243 jobs, but does not validate this unpublished successor. Publish eight refs through the normal hook, record the concrete review disposition, resolve the thread and require current-head CI before landing. Inline acknowledgement is 4466524022; thread remains open.
