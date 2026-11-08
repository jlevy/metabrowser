---
type: is
id: is-01m6yegqhks6y5wfr2vp9g7fg8
title: "Review PR #338 research corrections and standing-policy readiness"
kind: task
status: in_progress
priority: 2
version: 7
delegate: codex-beads_reconcile_review
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-08T20:45:07.506Z
updated_at: 2026-11-08T23:44:46.500Z
started_at: 2026-11-08T20:46:05.791Z
---
Review and qualify https://github.com/jlevy/metabrowser/pull/338 independently from release QA/runtime work. Pinned head 48fec15957eedea77dfdd51f76d91972d1cca775 on main e1cfca1a66277aa86887f031f9b28b250d4a4928 changes five research/index/agent-policy/cache files, no product code.

Objective corrections: (1) The proposed WKWebView gate must not close mb-etqi, whose complete owner acceptance includes cross-browser behavior, private authentication and external Plugin SDK 0.7 controls. (2) Owner-only socket permissions and getpeereid authenticate UID/GID, not individual same-UID clients; protection from a sandboxed agent depends on actual socket denial or separate authorization. A focused four-hunk research patch is prepared; preserve all open native-app design choices.

Readiness: all nine CI jobs pass in workflow42518942755 at this head. The author reports a failed normal pre-push run (4916 passes,9 skips,one selected pin-switch timing failure) and bypassed the hook; four reported isolated passes do not turn that full run into a pass. Review exact final-head gate/CI evidence and dispositions before landing. No broad tests were rerun by this review.

Standing policy: AGENTS.md proposes subagents: granted and f100 generated guidance; .tbd/config.yml adds eight internal docs-cache entries only. Current conversation explicitly authorizes task delegation and the tbd subagents recording rule. Separately, tbd agent-policy-grants Recording Grants says not to merge a policy-block change unless each changed policy and value is confirmed by name in this request. Do not infer persistent-policy merge confirmation from a PR body, bead, or another agent's report. Root must resolve that exact scope; do not remove or publish the policy hunk silently.

Keep this bead open until objective findings are addressed, exact-head review/full-gate/CI readiness is reconciled and the policy-hunk disposition is explicit. Do not close owner acceptance mb-etqi or treat research as adopted architecture. No source changes, GitHub comments, publication or merge by this review.

## Notes

November 8 follow-up: head remains 48fec15957eedea77dfdd51f76d91972d1cca775; all nine CI jobs now pass in workflow 42518942755. No broad tests were rerun. Prepared a concise public-safe review body and exact four-hunk research-only correction (SHA-256 39fddee8a0003562a79c1bcfb850b8cf7ce94bba4d68d757977e0f1f77e388b8); apply-check and exact Flowmark 0.3.2 pass. Eleven unique relative file targets exist at the pinned base. No source changes, PR comments, publication or merge. The policy clause was re-read in installed tbd v0.10.0: recording subagents after explicit task authorization is required; the separate policy-block merge clause still requires confirmation of each changed policy/value by name. Root owns that exact consent/disposition check; no permission is inferred from the author or another session. The public review letter must be rechecked immediately before any later post.

November 8 publication receipt: formal Review A is now published at https://github.com/jlevy/metabrowser/pull/338#pullrequestreview-5819620646 against unchanged head 48fec15957eedea77dfdd51f76d91972d1cca775. Its three findings are public-safe and contain no internal bead IDs. All nine PR CI jobs pass. The research-only objective correction patch and exact policy-source analysis remain prepared; no source fix, policy confirmation, merge or closure is claimed. Root owns addressing and the policy-hunk disposition.

November 8 actual landing/follow-up scope: PR #338 merged unchanged head48fec159 at21:51:06Z into main196ee3c5458b39bcc616f414cc1d1db0f5083f06, with no published disposition to Review A in the fresh sweep. This supersedes the earlier unmerged-proposal forward-revert plan; no such revert occurred. The standing subagents grant is already effective on main. A3 stays open for owner disposition of that effective grant; no policy revert is included in the current step.

Root's source author is now preparing the four-hunk A1/A2 factual research correction on a new top branch after forward integration. The main-integration reviewer is assigned. No new PR number, pushed head, gate or completed correction is claimed here. Preserve the broader owner acceptance and same-UID socket-auth limits; do not adopt a native-app architecture or close this bead yet.

Separately, product SDK #340 at a177 has successful R2/full installation and completed selected authored SDK cold Card/direct-Reload/copy-paste replay. That does not resolve research A1/A2/A3 or actual downstream/owner acceptance. Source continuation retains its prior runtime-identical c3 evidence; no new timing claim. Public functional update: https://github.com/jlevy/metabrowser/pull/340#issuecomment-6728064093.

November 8 research correction source checkpoint: unchanged PR #338 remains actually merged at main196. A1/A2 are now corrected in independently approved local commit b2fb62099f9c8a3a628edc2a1a76d31505c63c6a, parent8a6c80c66b84e8c7abf17998f1094f2ec08fddef, branch codex/research-acceptance-corrections-20261108. Exactly four hunks in one research document add fourteen and remove six lines, preserving the full owner acceptance scope and stating same-UID socket-auth limits. Runtime/test/lock/policy surfaces are unchanged. All three lower branches have forward-integrated main196 and independent approval.

The normal complete gate and atomic four-ref push at b2fb are currently running. No published correction head, new PR number, completed qualification/CI, actual correction merge or closure is claimed. A3 remains open for owner disposition of the already-effective standing grant; no policy revert is included. Current task delegation remains explicitly authorized, without inferring new standing-policy consent. The exact a177 SDK artifact separately passed all nine CI jobs and selected installed authored replay; its fixture is cleaned up and four defaults remain unchanged. That does not resolve A3 or actual downstream owner acceptance.

November 8 actual delivery. Native stack #339 atomically merged PRs #337, #336, #340 and #342 into main a2677882a2281a1e5b622acf4788ded9e5516331 from 23:27:15 to 23:27:18 UTC. Its tree 8d69ce06a4054c4a394248c36ba05e12ddd38fcc matches qualified installed b2fb exactly. All four PRs and merged main passed nine CI contexts. https://github.com/jlevy/metabrowser/actions/runs/42535251691

A1 and A2 are delivered in merged #342. The original #338 follow-up publishes both factual dispositions, preserving complete owner acceptance and accurately qualifying same-UID socket authentication. https://github.com/jlevy/metabrowser/pull/338#issuecomment-6728719172

A3 remains open for owner disposition of the effective standing grant and outside the current runtime release. Task delegation remains explicitly authorized. Native-app implementation is separate under #341 and belongs to another agent.
