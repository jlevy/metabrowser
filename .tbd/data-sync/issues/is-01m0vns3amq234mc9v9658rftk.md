---
type: is
id: is-01m0vns3amq234mc9v9658rftk
title: Git commit diffs disappear when the diff plugin has not been loaded
kind: bug
status: open
priority: 1
version: 1
labels:
  - git
  - regression
  - browser
dependencies: []
created_at: 2026-08-25T05:20:07.496Z
updated_at: 2026-08-25T05:20:07.496Z
---
Reproduced on released v0.7.0 against commit 7a4b588: clicking a Git history row opens /commit/<sha> and renders the commit header, but no changed-file diff. The same repository and commit on v0.6.0 render 1 diff file and 16 diff lines. In v0.7.0, src/metabrowser/static/git-panel.js mountCommitDiff() calls getRegisteredView("diff", "diff") without first awaiting ensureKindAssets("diff"); because commit c3b724b moved all plugin assets to on-demand loading, the lookup returns null on a fresh directory view and the host is silently removed. Add an end-to-end/browser regression covering a fresh session, Git tab, and first commit click.
