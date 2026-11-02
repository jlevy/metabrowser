---
type: is
id: is-01m6f2wpcg46c1r6skezq0xyq9
title: A transient /api/git/repo failure removes the Git panel for the rest of the page
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6ezt071eh0dj86tf6rct9w6
created_at: 2026-11-02T21:33:20.140Z
updated_at: 2026-11-02T21:33:20.140Z
---
ensureHistory calls teardown() whenever fetchRepoInfo returns null (static/git-panel.js, the comment says 'The served root stopped being a repository under us'), and fetchRepoInfo returns null for a failed request as well as for is_repo false, so one 503 or a dropped connection removes the Git tab and its popstate listener until the page reloads. v0.11.0 has the same code on the tab's onShow path. PR #275 (mb-y1p5) makes every Back or Forward onto a /commit/ entry call the gate, so the window is wider there. Review B finding B3 reported it (https://github.com/jlevy/metabrowser/pull/275#pullrequestreview-5743570259); PR #275 fixed only the part it owns: a landing no longer paints a commit after the panel is gone. Remaining: tell a failed gate from one that says is_repo false, and tear down only on the second. A second concurrent ensureHistory that gets a good answer after the first tore down also runs refreshHistory on the reset state; the same fix removes it. tests/dom/git-commit-history-session.js pins the current behavior in the step 'a landing when the repository gate failing once'.
