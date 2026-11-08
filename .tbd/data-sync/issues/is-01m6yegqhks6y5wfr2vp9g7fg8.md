---
type: is
id: is-01m6yegqhks6y5wfr2vp9g7fg8
title: "Review PR #338 research corrections and standing-policy readiness"
kind: task
status: in_progress
priority: 2
version: 3
delegate: codex-beads_reconcile_review
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-08T20:45:07.506Z
updated_at: 2026-11-08T20:47:44.564Z
started_at: 2026-11-08T20:46:05.791Z
---
Review and qualify https://github.com/jlevy/metabrowser/pull/338 independently from release QA/runtime work. Pinned head 48fec15957eedea77dfdd51f76d91972d1cca775 on main e1cfca1a66277aa86887f031f9b28b250d4a4928 changes five research/index/agent-policy/cache files, no product code.

Objective corrections: (1) The proposed WKWebView gate must not close mb-etqi, whose complete owner acceptance includes cross-browser behavior, private authentication and external Plugin SDK 0.7 controls. (2) Owner-only socket permissions and getpeereid authenticate UID/GID, not individual same-UID clients; protection from a sandboxed agent depends on actual socket denial or separate authorization. A focused four-hunk research patch is prepared; preserve all open native-app design choices.

Readiness: all nine CI jobs pass in workflow42518942755 at this head. The author reports a failed normal pre-push run (4916 passes,9 skips,one selected pin-switch timing failure) and bypassed the hook; four reported isolated passes do not turn that full run into a pass. Review exact final-head gate/CI evidence and dispositions before landing. No broad tests were rerun by this review.

Standing policy: AGENTS.md proposes subagents: granted and f100 generated guidance; .tbd/config.yml adds eight internal docs-cache entries only. Current conversation explicitly authorizes task delegation and the tbd subagents recording rule. Separately, tbd agent-policy-grants Recording Grants says not to merge a policy-block change unless each changed policy and value is confirmed by name in this request. Do not infer persistent-policy merge confirmation from a PR body, bead, or another agent's report. Root must resolve that exact scope; do not remove or publish the policy hunk silently.

Keep this bead open until objective findings are addressed, exact-head review/full-gate/CI readiness is reconciled and the policy-hunk disposition is explicit. Do not close owner acceptance mb-etqi or treat research as adopted architecture. No source changes, GitHub comments, publication or merge by this review.

## Notes

November 8 follow-up: head remains 48fec15957eedea77dfdd51f76d91972d1cca775; all nine CI jobs now pass in workflow 42518942755. No broad tests were rerun. Prepared a concise public-safe review body and exact four-hunk research-only correction (SHA-256 39fddee8a0003562a79c1bcfb850b8cf7ce94bba4d68d757977e0f1f77e388b8); apply-check and exact Flowmark 0.3.2 pass. Eleven unique relative file targets exist at the pinned base. No source changes, PR comments, publication or merge. The policy clause was re-read in installed tbd v0.10.0: recording subagents after explicit task authorization is required; the separate policy-block merge clause still requires confirmation of each changed policy/value by name. Root owns that exact consent/disposition check; no permission is inferred from the author or another session. The public review letter must be rechecked immediately before any later post.
