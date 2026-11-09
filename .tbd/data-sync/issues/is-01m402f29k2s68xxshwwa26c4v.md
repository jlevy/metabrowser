---
type: is
id: is-01m402f29k2s68xxshwwa26c4v
title: Execute the full v0.12 QA runbook on a pinned post-landing candidate
kind: task
status: in_progress
priority: 1
version: 9
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
hold: null
hold_until: null
created_at: 2026-10-03T05:05:53.458Z
updated_at: 2026-11-09T01:24:52.220Z
started_at: 2026-11-08T03:02:07.630Z
---
Run setup/doctor including negative controls, full make verify, admitted Git/macOS/live-GitHub tiers, refusal checks, plain-folder features in real browsers, acquisition/cache/pins/trust, GitHub URLs and PR pages, refresh/ref switching/offline reopening, and regression comparisons. Record step-level pass/fail/blocked/untested. Keep caches and temporary outputs on external scratch and durable evidence outside scratch.

## Notes

November 8: installed 426 functional smoke passed

Both default CLI aliases now use exact gated 0.11.1.dev1287+426ce7b62, installed offline without rebuilding or upgrading dependencies. Doctor reports 11 healthy plugins. All 33 served-asset matches, 45 applicable dependency pins, operator PATH checks and unchanged skill-content/manual-provenance checks passed. The managed preview selects merged main e1cf; filesystem targets, caches, configuration and local changes remain intact.

Freshly reloaded built-in browser sessions passed PR #335: nine successful checks in both source modes, its two-file comparison (+63/-10) in managed mode, and latest merged commit e1cf with the same file and line totals in checkout mode. Switching tabs independently restores PR #335/Checks and commit e1cf. The original CHANGELOG.md card and first Document tab share the 323.994 px left edge, with 40 px horizontal inner padding and the table of contents on the right. All three freshly reloaded sessions had empty warning/error logs during this smoke.

Receipts: metabrowser-installed-gated-release-docs-426ce7b62-20261108/{installation,post-verification,browser-smoke}.json. This is functional evidence; the full final QA runbook and owner matrix remain open. The historical 1ede managed refresh warning at 2,014 ms remains unresolved evidence.

November 8: installed 1ede functional session

Exact gated wheel 0.11.1.dev1283+1ede1e220 is installed for both aliases; doctor11, all33 live-asset comparisons and45 applicable runtime pins passed. The managed preview selects mergedmainfe04; both filesystem targets and normal cache/config remain intact. Built-in browser passed PR334 Conversation, Changes (six files, +321/−20) and Checks (nine successes) in managed and checkout modes. Checkout Commit9416 renders four changed files and restores independently from PR334/Checks. Quick Search bare#, #retain and#334 completes across cached PR states and Enter opens334. Original CHANGELOG.md selection remains at8411, card/tab left edge323.994px, innerpadding40px and right TOC.

Current-build warnings/errors: none on8411/8864 after installation cutoff; one managed8863 slow pull-refresh warning (2014 ms, server2010 ms,1598-byte response) retained for mb-4ifm. No source error, but no latency acceptance claim. Raw installation/postcheck receipts are in metabrowser-installed-gated-mechanism-1ede1e220-20261108; browser receipt is b0aq-mechanism-20261108/installed-browser-verification.json. Full final-release QA and owner matrix remain open; earlier H2 missing-gh proof stays at its original artifact identity.

Installed H2 (a2bb0d29a, version 0.11.1.dev1280+a2bb0d29a) negative setup check passed: isolated child PATH excludes gh; Pulls returns typed gh_missing with one visible setup message and official install link, plus clipped polite live announcement. Files and local Commits continue functioning; selected afaf rendered 4 files with no busy state. Initial 0755 fixture cache/config correctly refused, then fixture-only permissions corrected to0700 before test. No auth, global PATH or normal cache/config changed. Receipt: metabrowser-installed-gh-missing-20261108/functional-receipt.json with raw pulls.json. Temporary8917 server verified/stopped SIGINT130 and tab closed. Functional scope only; full pinned release runbook remains open.

November 9 source-equivalent browser checkpoint. Space commit a53907948f348345ea0c6cbafbfe138c6513ba70, tree cdb95f003ddddceb9d231e194b88658962551a1f, parent a1f8393b04a378e5ba25d8dabefd4f4020fa03a3. The functional session ran in a patched scratch source checkout and locked environment with equivalent tree content. Evidence: release-followups-r3-20261108/source-browser-session.json.

Built-in source-browser checks passed on public pallets/markupsafe: blob Source lines 1–3, catalog totals, #507 Space disclosure and nested/Files folder controls, Checks retained through Reload and scheduled watch, and warm blob reopen without another clone. Disposable malformed config refused without changing config/cache and recreated canonical config on retry while reusing the repository cache.

A disposable local pin passed cold acquire, fetch without pin movement, explicit Switch, branch/tag retention and root fallback, head/parent diff links and Back with coherent pin/controls. Untrusted HTML was Source only, the raw marker stayed inert, raw nosniff/sandbox were present, cache-list returned 409 and null-origin source status returned 403. After moving the local origin, the cached tip and Markdown reopened with a typed refresh warning. The fixture listeners stopped and the local origin was restored. This is functional evidence on source. Qualified-wheel QA, the live account upgrade, private access, public GitHub offline reopen, stock-browser back/forward-cache and timing remain separate.

November 9 pre-merge checkpoint.

The normal R3 full gate and atomic two-ref push passed in 1,444.45 seconds, with 4,931 Python passes, nine expected skips, 388 goldens, clean audits and packaged-wheel checks. Both CLI aliases now run 0.11.1.dev1308+a53907948, tree cdb95f003ddddceb9d231e194b88658962551a1f, wheel SHA-256 2aa96c7924e4bd4c52836a0b91086f12d2b076b1cb5d8b5045ab30821dc6684e.

The authorized private one-account upgrade changed exactly 17 headers in place and preserved settings, record bodies, modes, cache identity and nine Git-directory fingerprints. Five healthy previews were verified. The full release and merged-main checks remain separate.

The installed in-app browser confirmed Space disclosure false → true → false in both checkout PR #337 and managed PR #336, retaining focus, the address and Checks. The default preview rendered Treemap folder totals.

This is the scoped installed check. Complete installed and owner QA are still open.

Evidence: release-followups-r3-20261108/stack345-merge-readiness.json, installed-iab-receipt.json and qualified-55-receipt.json. Quiet preflight evidence: host-a539-20261109T011536Z-decision.json.
