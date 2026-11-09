---
type: is
id: is-01m6yvdd0vjh112keerpr3gpc7
title: Toggle focused collapsible navigation rows with Space
kind: bug
status: closed
priority: 1
version: 6
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-09T00:30:29.914Z
updated_at: 2026-11-09T01:34:47.280Z
closed_at: 2026-11-09T01:34:47.280Z
close_reason: "Reviewed and verified in PRs #343 and #344. Owner-approved stack #345 merged into main at 87b8ec812774bb12a4d9f5f29901719b8b66d323 with the same tree as the qualified installed wheel. All 18 PR CI jobs passed. Merged-main CI and release gates remain on the release tracker."
resolution: null
duplicate_of: null
---
Space on a focused expandable PR row should expand or collapse the changed-file tree, matching Files and Commits. Preserve selection, focus, and the current page. Do not intercept native Space activation on nested buttons or scroll the page. Audit other collapsible navigation rows and verify the keyboard path in a browser and a focused regression.

## Notes

November 9 source-equivalent browser checkpoint. Space commit a53907948f348345ea0c6cbafbfe138c6513ba70, tree cdb95f003ddddceb9d231e194b88658962551a1f, parent a1f8393b04a378e5ba25d8dabefd4f4020fa03a3. The functional session ran in a patched scratch source checkout and locked environment with equivalent tree content. Evidence: release-followups-r3-20261108/source-browser-session.json.

Independent S1 re-review approved. The handler uses the focused mounted row, even when a background catalog update moved the tab stop. Nine focused goldens, twelve pytest cases, parity and browser types passed. Startup remains 20 requests and 178,592 bytes.

In the built-in browser with public pallets/markupsafe PR #507, Enter opened Checks and Space toggled the focused PR disclosure while retaining focus and address. Reopening revealed five changed files. Space also operated the nested changed-file folder and the Files tab docs folder. Manual Reload disabled during refresh and retained the selected and expanded PR and Checks. The scheduled watch showed stale-refreshing state followed by success. The full normal R3 gate and atomic two-ref push are running in a dedicated environment at this commit. Exact wheel, CI and merged delivery remain pending.

November 9 pre-merge checkpoint.

The normal R3 full gate and atomic two-ref push passed in 1,444.45 seconds, with 4,931 Python passes, nine expected skips, 388 goldens, clean audits and packaged-wheel checks. Both CLI aliases now run 0.11.1.dev1308+a53907948, tree cdb95f003ddddceb9d231e194b88658962551a1f, wheel SHA-256 2aa96c7924e4bd4c52836a0b91086f12d2b076b1cb5d8b5045ab30821dc6684e.

The installed in-app browser confirmed Space disclosure false → true → false in both checkout PR #337 and managed PR #336, retaining focus, the address and Checks. The default preview rendered Treemap folder totals.

Stack #345 is ready for the exact forward atomic merge into main a2677882. PR #343 at a1f8393b04a378e5ba25d8dabefd4f4020fa03a3 has nine green CI jobs in 42543688913. PR #344 at a53907948f348345ea0c6cbafbfe138c6513ba70 has nine green jobs in 42543714994. Independent reviews are verified and no threads remain unresolved. Automatic review rejected the merge command because the retained owner handoff requires approval for this exact stack. Both PRs remain open and owner merge approval is pending.

Evidence: release-followups-r3-20261108/stack345-merge-readiness.json, installed-iab-receipt.json and qualified-55-receipt.json. Quiet preflight evidence: host-a539-20261109T011536Z-decision.json.
