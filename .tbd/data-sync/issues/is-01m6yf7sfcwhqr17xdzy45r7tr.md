---
type: is
id: is-01m6yf7sfcwhqr17xdzy45r7tr
title: Ensure SDK template renderers work on direct plugin-page loads
kind: bug
status: in_progress
priority: 1
version: 6
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
updated_at: 2026-11-08T21:58:22.275Z
started_at: 2026-11-08T21:02:13.494Z
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
