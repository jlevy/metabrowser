---
type: is
id: is-01m6wdjwawp9g1bvnefz2hxze3
title: Prepare the next Metabrowser release candidate without publishing
kind: task
status: in_progress
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m5wdbsy6z6d95sgg03kwmm76
child_order_hints:
  - is-01m6wtacta0gcph1j42jw3vq26
  - is-01m6xby4qhb8m9fk5zd9x3tg5p
hold: null
hold_until: null
created_at: 2026-11-08T01:50:20.508Z
updated_at: 2026-11-08T15:46:10.980Z
started_at: 2026-11-08T01:55:06.900Z
---
Prepare Metabrowser 0.12.0 under release coordinator mb-4bd2. Product layers through PR #334 are merged, reviewed, CI-green and installed. Finish the separate release-documentation correction mb-y489 and its full gate, independent reviews, PR/CI and merge. Then freeze the exact candidate for final data/audit/browser differentials mb-2g6f, the above-50-file comparison mb-8pyc, quiet previous-release rehearsal mb-cf6y, navigation and large-PR qualification mb-4ifm, the complete installed-wheel runbook mb-m20f and owner matrix mb-etqi. Keep docs, plans, skill identity, changelog and the behavior-change record current; prepare complete 0.11.0-to-0.12.0 release notes and a concrete artifact/checklist packet. Preserve historical failed, interrupted and invalidated observations at their original source identities. No tag, GitHub release, PyPI publication or post-publication claim before the owner's approval of the exact final commit and notes. Future Files source/branch workflow mb-itzy remains paused and outside this scope.

## Notes

November 8: latest reviewed product and documentation layers merged

PR #334's prefetch producer/pass ownership fixes are merged as fe04 and installed from exact gated1ede, with functional browser checks and all PR/main CI green. PR #335's release-command and trust documentation corrections passed local full verification (4,917 tests, nine expected skips, 386 goldens, audits/distribution/installed-wheel checks), independent senior/security reviews and all nine PR CI checks. It merged as e1cfca1a66277aa86887f031f9b28b250d4a4928 with exact gated426 tree; post-merge main CI is running. mb-y489 stays open until that receipt is checked.

No non-reference product PR remains open; draft #247 is explicitly excluded. Exp-057 is now collecting the exact426 wheel against published0.11.0 in fresh benchmark-only environments, with quiet-host and original hard-gate rules. Navigation hypothesis measurements, final data/audit/browser differentials, installed final QA and the owner acceptance matrix remain open. The two-second managed pull-refresh warning has not been explained or accepted as fast. mb-itzy remains paused and outside current implementation. No tag, release or publication is authorized.

November 8: PR334 complete; release docs gating

PR #334 merged at fe04a4b1c with the reviewed 1ede1e220 tree, full verification and all nine PR/main CI jobs green. Exact wheel is installed and both repository-mode functional sessions pass. The scoped correctness beads mb-b0aq/mb-ygiq are closed. A retained 2-second managed refresh warning remains a performance qualification under mb-4ifm, not an accepted timing result.

The separate mb-y489 layer changes only README.md and docs/publishing.md. Independent senior and security/process reviews approve it; a forward merge of main preserved its exact reviewed content. Complete normal pre-push make verify is active at426ce7b62. No installer was executed by documentation validation. After its PR/CI and merge, freeze the release candidate for the remaining differentials, quiet performance, full installed QA and owner acceptance. No release/tag/publication; mb-itzy remains paused.

November8 current release-preparation checkpoint

All product layers through PR333 are merged and installed as a2bb0d29a on main9416. Source/cached-checkout browser checks and missing-gh isolated installed QA pass. New prefetch ownership work is frozen at1ede1e220; independent review found B1at ea1c and confirmed its forward correction (600/599/600coverage, delayed receipt/release), no open review findings. Full exact-head normal prepush makeverify is active; no PR/CI/install success claimed yet. Static release audit found three documentation gaps now tracked together as mb-y489: scoped fresh-release probe exemption, public skill installer/source pins, README trust summary. No new product defect or untracked acceptance gate was found.

Quiet exp057 collected zero pairs after host preflight deferred; final three differentials, performance qualification, full installed QA and owner matrix remain open. No tag or release. Future source/branch workflow mb-itzy remains paused.

November 7 UI checkpoint at 24f3721c9: shared bold normal-text-color actor/repository names; sidebar author/repo metadata12px, page actor/action/age14px; commit history/page/tooltip migrated. Stack list badge beside PR number; page menu right of state badge, bold position · title · PR number; leading GitHub brand action; Reload right of filters, Updated line retained. Independent review found a P2 keyboard issue in the Reload move; failing real-production-session regression reproduced, chip iteration corrected, green afterward. Final focused61 Git/PR/design tests, earlier85 PR/stack/design tests and nine focused golden scenarios passed; full lint/types passed. Built-in browser confirmed sizes/color/weight, menu fit at750px actual CSS viewport, Reload tabIndex0/no aria-checked. Exact-head full gate, published CI and final installation remain required. Corresponding acceptance beads mb-am7d,mb-x1v5,mb-4kpu,mb-xvz2 stay open. Lower release-prep c67371c2 independently reviewed with no findings. Original28-layer stack is merged at68534af93; this new follow-up stack is not yet published. Experiment056 stopped on a valid444ms candidate first-row result exceeding350ms hard budget; preserve it, no complete paired verdict. Release remains unpublished pending further gates and owner approval.
