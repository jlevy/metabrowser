---
type: is
id: is-01m2h5fck4qrqnzvmwebdwjvnt
title: Hand-verify v0.10.0 in a real browser before tagging
kind: task
status: closed
priority: 1
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01m2fafd1v8d5pakt6r7zxw5n8
created_at: 2026-09-14T23:54:11.428Z
updated_at: 2026-09-15T01:46:15.972Z
closed_at: 2026-09-15T01:46:15.972Z
close_reason: "All six hand checks pass against the candidate; results recorded on the bead. Check 3b (automatic recovery after a restart) failed first and uncovered mb-fmlr, fixed and merged in PR #127."
resolution: null
duplicate_of: null
---
Before tagging v0.10.0, check by hand in a real browser on the release candidate: J and K in the file tree (Files and Recent) and in the Git history; the preview's loading spinner, and 'Metabrowser is not reachable' followed by automatic recovery when the server stops and restarts; a Markdown task-list note with [[wiki]] links and ![[embeds]]; tree and Git rows aligned on a shared text baseline; and metab --version for a wheel installed in a .venv inside a git repository, which must print no dev-build annotation (mb-7nij). Record the evidence in exp-034 or the release-prep PR.

## Notes

All six hand checks run against the candidate on 2026-09-15, in headed Chromium 141 under Xvfb, driven through the DevTools Protocol against a purpose-built git fixture (7 commits, a Markdown note with a task list carrying [[wiki]] links and an ![[embed]]).

1. J and K move the selection down and up in the file tree and in the Git history, the same way the arrow keys do: PASS, 8 sub-checks.
2. The preview pane shows a loading indicator rather than the old 'Select a file to preview.' text: PASS.
3. 'Metabrowser is not reachable.' appears when the server stops: PASS. Automatic recovery when it restarts: FAILED, then PASSED after the fix in mb-fmlr. The restarted server was binding the next port up, so the page polled a port nothing served.
4. A Markdown task-list note with [[wiki]] links and ![[embeds]]: PASS. Wiki links inside task-list items convert (3), an ordinary link beside them survives (2), checkboxes render (3), and the embed transcludes the embedded note's own text.
5. Tree and Git rows on a shared text baseline: PASS, measured directly rather than by heuristic. A zero-height inline-block probe reports the alphabetic baseline: a tree row gives name@13px=159.5, size@12px=159.5; a git row gives subject@13px=117.75, age@12px=117.75. Identical to the hundredth of a pixel across four rows of each.
6. metab --version for the candidate wheel installed in a .venv inside a git repository prints 'metab 0.9.2.dev201+03fd7997' with no dev-build annotation: PASS (mb-7nij).

Two things the checks got wrong before they were right, both recorded so the harness is not trusted blindly: the first baseline assertion compared a ratio of top offsets and flagged every row, and a later one probed .git-graph-meta, a flex container whose zero-height probe becomes a flex item rather than inline content. Neither was a product fault; the git ref chip is centred deliberately and is not one of the two text sizes the claim is about.
