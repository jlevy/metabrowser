---
type: is
id: is-01m6yvdd0vjh112keerpr3gpc7
title: Toggle focused collapsible navigation rows with Space
kind: bug
status: in_progress
priority: 1
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-09T00:30:29.914Z
updated_at: 2026-11-09T00:50:42.826Z
---
Space on a focused expandable PR row should expand or collapse the changed-file tree, matching Files and Commits. Preserve selection, focus, and the current page. Do not intercept native Space activation on nested buttons or scroll the page. Audit other collapsible navigation rows and verify the keyboard path in a browser and a focused regression.

## Notes

November 9 source-equivalent browser checkpoint. Space commit a53907948f348345ea0c6cbafbfe138c6513ba70, tree cdb95f003ddddceb9d231e194b88658962551a1f, parent a1f8393b04a378e5ba25d8dabefd4f4020fa03a3. The functional session ran in a patched scratch source checkout and locked environment with equivalent tree content. Evidence: release-followups-r3-20261108/source-browser-session.json.

Independent S1 re-review approved. The handler uses the focused mounted row, even when a background catalog update moved the tab stop. Nine focused goldens, twelve pytest cases, parity and browser types passed. Startup remains 20 requests and 178,592 bytes.

In the built-in browser with public pallets/markupsafe PR #507, Enter opened Checks and Space toggled the focused PR disclosure while retaining focus and address. Reopening revealed five changed files. Space also operated the nested changed-file folder and the Files tab docs folder. Manual Reload disabled during refresh and retained the selected and expanded PR and Checks. The scheduled watch showed stale-refreshing state followed by success. The full normal R3 gate and atomic two-ref push are running in a dedicated environment at this commit. Exact wheel, CI and merged delivery remain pending.
