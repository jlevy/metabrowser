---
type: is
id: is-01m6yf7sfcwhqr17xdzy45r7tr
title: Ensure SDK template renderers work on direct plugin-page loads
kind: bug
status: closed
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex/prefetch_ownership_review
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-08T20:57:43.147Z
updated_at: 2026-11-08T23:44:47.346Z
started_at: 2026-11-08T21:02:13.494Z
closed_at: 2026-11-08T23:44:47.345Z
close_reason: "SDK cold direct-entry fix delivered in PR #340 with authored installed replay and merged-main CI."
resolution: null
duplicate_of: null
---
Installed c3 authored SDK 0.7 sample works after navigating from folder Overview, but direct reload of the public long-controls.md plugin page renders Could not display this view. Console records metabrowser.render: Mustache.js is not loaded — bundle is missing at plugin-sdk.js456, sample index.js30, view-composition mount151 and app6035. Both fixture manifest and styles match the existing public sample; it uses the documented synchronous SDK render helper. First establish whether the SDK or plugin asset-declaration contract owns template readiness, reproduce a focused regression and use existing asset loading/lifetime mechanisms. Do not add speculative compatibility or an unconditional large eager dependency. Preserve original console and failed reload. Independently review the smallest correct fix, normal complete gate and current installed direct-entry/browser replay. This is separate from measured large-source continuation and actual downstream owner migration.

## Notes

Cold-entry diagnosis confirms a host readiness gap: the public synchronous render helper requires Mustache, but plugin loading awaits sdk-views while Mustache is left to a best-effort idle chain. Prepare the smallest explicit readiness repair with a real red regression; current source remains unchanged while the earlier QA gate completes. Direct-reload console/DOM/image evidence is preserved under authored-sdk07-controls-20261108/manual-c3-20261108. All copy/paste and both continuation paths pass independently; full SDK acceptance remains blocked by the direct-entry failure.

November 8 follow-up: SDK implementation d69e3e71f is independently reviewed (13 blobs unchanged), with 44 focused passes, one golden, both browser type projects, parity and the unchanged startup ceiling passing at178592 bytes. Eight live public GitHub checks pass in53.25 seconds. Normal full-gate R1 is FAILED, not qualification:4929 passed,2 failed,9 expected skips in1056.09 seconds; no golden stage, audit/build, artifact, push or installation followed. Both failures are the existing preview-session NoPlugin fallback assertions. Diagnostic whole-module evidence proves its fixture omitted the new named Mustache bundle, yielding Unknown asset bundle before any library request. A three-file test-only correction restores the original NoPlugin messages, keeps core-only requests and helper retry behavior, and adds template refusal/retry coverage; no production change. Current focused recovery passes52 tests in2.72 seconds, both type projects and parity. All-golden preflight and independent follow-up are running before a forward commit and full R2 gate. Original failed gate and diagnostic attempts are preserved. The installed c3 build and four global-venv servers remain unchanged; the additional concurrent8412 URL will be preserved during eventual controlled restart. No new SDK artifact, promotion, PR or release acceptance yet.

November 8, SDK readiness R2 checkpoint: clean forward commit a17752dd9695b3cdd4ed17926b6c0289cfd60fc0 contains the unchanged thirteen implementation blobs approved in Review A plus three fixture-only blobs approved in Review B. The original d69 normal full gate R1 failed two existing preview No Plugin assertions, with 4929 passes and nine skips; it stopped before goldens, audits, artifact build or push. R1 remains failed and supplied no qualified artifact.

The preview fixture omitted the real Mustache bundle that the production server publishes. The three-file correction uses the actual library and asset loader, retains both original No Plugin assertions and every existing displayed state, adds four expected request-list entries and one real template failure/retry scenario. It changes no production code. Integrated preflight passes 52 focused tests in 2.72 seconds, all 388 goldens in 230.78 seconds, both type projects and parity. The second normal full gate/push is running in root session 30931; no completion, new SDK PR, installer GO, qualified wheel, installation or cold direct-view replay is claimed.

Remote native stack #339 still has exactly two members: PR #337 at c3 then QA PR #336 at 0a. Both are reviewed and all nine CI jobs are green. The SDK successor will be published only after its normal push gate completes. The vnm1 release blocker remains open pending the actual qualified artifact, CI, installation, cold replay and merge reconciliation.

All global server preparation includes four ports: 8411, 8864, 8863 and concurrent 8412, whose effective target matches 8411. All remain on installed c3 now. The user authorized updating all; root will preserve each URL, target, configuration and working directory, including 8412, through controlled restart only after a qualified-wheel GO. No server or installation change has occurred in this checkpoint. The earlier 45 asset comparisons cover the three audited previews, not a new four-server validation.

Historical 426 differential acceptance and raw exceptions remain separate. Quiet performance, source warning attribution under mb-06p9/mb-4ifm, Step9, the full installed owner matrix and exact final release approval remain open. No latency pass, c3 regression origin, release tag or publication is inferred. The mb-itzy workflow remains paused and reference draft #247 excluded.

November 8, qualified SDK R2 delivery (no closure before actual merge): exact a17752dd9695b3cdd4ed17926b6c0289cfd60fc0 passed normal full make verify/push in 1493.61 seconds, with 4931 Python passes, nine expected skips, 388 goldens, clean types/locked audits/distribution/smokes and zero-byte filesystem observer. Original d69 R1 remains failed with two fixture assertions and no qualified artifact or push. Review A is published at https://github.com/jlevy/metabrowser/pull/340#pullrequestreview-5819928655 and Review B at https://github.com/jlevy/metabrowser/pull/340#pullrequestreview-5819928920, covering unchanged reviewed blobs.

SDK PR #340 is now the third member of native stack #339 above #336 and #337, exact a177 on QA0a. Its current CI workflow 42529805379 is running; prior #337/#336 exact heads retain nine green jobs and reviews. All three are drafts in the current metadata snapshot. No merge readiness is inferred from a successful local gate alone.

Both global CLI aliases and all four known servers (8411,8864,8863,8412) now run exact qualified wheel 0.11.1.dev1296+a17752dd9, SHA-256 e6971cfca83f37b84761ef847ed9a358a7723c5301a339b19f153a6f44d42df0. Doctor eleven, 45 unchanged runtime pins, 349 payload files, 355 installed RECORD hashes and 68 served-asset matches pass. Existing targets/configuration/working directories and port8412 URL were preserved. Managed data remains snapshot e1cf, distinct from application source.

The first literal cold entry on reserved fresh origin8986/long-controls.md passes the expected heading, Card, copy control and paste field without the prior Mustache error; root is continuing the full authored SDK replay. That initial result does not complete cold Reload/continuation checks, actual downstream SDK migration, the owner matrix or performance acceptance. Keep vnm1 open until completed replay, exact current CI and actual merge reconciliation.

Fresh remote facts supersede the prior unmerged-research plan: #338 merged unchanged48fec at21:51:06Z into main196ee3c5458b39bcc616f414cc1d1db0f5083f06. Review A findings A1/A2/A3 have no published disposition in the fresh sweep. The standing grant is now effective on main, so the earlier still-ineffective-proposal revert rationale is not an operation already performed. Main196 is not an ancestor of lower c3, even though GitHub reports337/336 CLEAN; root owns the forward-base incorporation and propagation decision, with actual resulting qualification/CI. No refs or source are changed by these notes.

Historical426 differential acceptance/raw exceptions, c3 manual evidence, slow-fetch/Source/poller diagnostics, quiet release/navigation/large-PR/Step9, full installed QA and owner release approval remain separate. No latency pass, new regression-origin claim, release tag or publication. The mb-itzy workflow remains paused and reference247 excluded.

November 8 forward-integration checkpoint: all nine SDK a177 CI jobs pass in workflow 42529805379 and its watch exited zero. The selected installed authored SDK replay is complete: cold long Card, long/small direct Reload, exact 38-character short and 2,960,074-character long copy/paste through final row 040000, initial Source 524,288 characters and two continuation controls. Full Source continuation retains its earlier unchanged-renderer c3 proof and was not rerun at a177; inspection deadlines remain preserved with no timing claim. Product stack menu and Checks-preserving selection pass. Fixture tab 74 is closed; identity-verified PID 79738 received SIGINT, and process/listener 8986 are absent. The four global servers and installed 0.11.1.dev1296+a17752dd9 remain unchanged. Authored integration coverage does not complete actual downstream/owner acceptance.

Main196 forward merges are complete locally: PR #337 head308d72c460ce7d3494c3e169e719759bda5f7388, #336 head5784d8031e5f07fdb68051d2e80b050c013cd399, #340 head8a6c80c66b84e8c7abf17998f1094f2ec08fddef. Each merge increment equals the exact five documentation/policy paths from main and preserves 974 runtime/test entries and the original layer delta. Independently approved fourth local layer b2fb62099f9c8a3a628edc2a1a76d31505c63c6a on codex/research-acceptance-corrections-20261108 contains only four A1/A2 research correction hunks in one document, fourteen added and six removed lines. All four local heads are independently approved.

The normal full gate and atomic, non-force four-ref push at b2fb are running; no completion, new integrated-head qualification/CI, published heads or new fourth-layer PR number is claimed. Installation remains a177. Actual merges and exact-head reconciliation are still pending, so this bead is not closed. Research #338 is already merged; A3 remains open for owner disposition of the effective standing grant, and this step contains no policy revert or native-app architecture adoption. Quiet performance, Step9, complete installed QA, owner acceptance and exact final release approval remain open; mb-itzy stays paused and reference draft #247 excluded.

November 8 actual delivery. Native stack #339 atomically merged PRs #337, #336, #340 and #342 into main a2677882a2281a1e5b622acf4788ded9e5516331 from 23:27:15 to 23:27:18 UTC. Its tree 8d69ce06a4054c4a394248c36ba05e12ddd38fcc matches qualified installed b2fb exactly. All four PRs and merged main passed nine CI contexts. https://github.com/jlevy/metabrowser/actions/runs/42535251691

The reviewed SDK template readiness fix and its fixture-only follow-up landed in #340. The installed a177 authored fixture passed cold literal Card, direct Reload and exact 38-character and 2,960,074-character copy/paste. Full Source continuation retains unchanged-renderer c3 evidence. The original R1 failure is preserved and downstream owner acceptance is separate.
