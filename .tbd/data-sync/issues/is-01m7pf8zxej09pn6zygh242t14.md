---
type: is
id: is-01m7pf8zxej09pn6zygh242t14
title: "Checkout branch chooser: a folder that is a repository's root shows the mirror's branch and tag chooser; any branch, tag, or remote-tracking branch, the checked-out one included, is viewed read-only as a pinned revision from the checkout's own .git, never written; the Working tree is a separate row and the default; metab PATH --ref NAME opens on a ref"
kind: feature
status: closed
priority: 1
version: 13
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/559
    at: 2026-11-20T17:04:03.881Z
delegate: claude-code@spud10
labels:
  - linear
dependencies:
  - type: blocks
    target: is-01m6wpacpj9wtx02rt1g8kx49m
parent_id: is-01m7wys615s2mfvbc93c9g2pac
hold: null
hold_until: null
created_at: 2026-11-18T04:40:08.878Z
updated_at: 2026-11-20T19:11:46.986Z
started_at: 2026-11-18T04:41:02.677Z
closed_at: 2026-11-18T18:38:40.832Z
close_reason: "Merged in #559 (aa7808b80) after reviews A-C."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 98672d9f-8697-447b-856c-c14323ce87e0
    linked_at: 2026-11-20T18:00:51.303Z
---
Owner, 2026-11-18 in chat: 'Why do I still not see a branch chooser anymore? ... I'm looking at a local repo ~/wrk/aisw/tradekb'. The chooser (static/source-ref-selector.js, #236/mb-eezo) renders only for a pin served from a mirror (server.py: git_pin and mirror_session). Owner chose: view the picked ref read-only from the checkout's .git as a pinned revision; never git checkout. Coordinate with Open Modes (mb-wup3, plan-2026-11-02-pr-review-mirror-and-checkout.md) and the pin model (/api/source/pin, #511's View on branch).

## Notes

2026-11-18 owner (chat): 'In general, when running in mirror mode, the working copy should never have changes. When running in file or folder mode, we would want to be able to view all the other branches as if it's in mirror mode, but it would be all within the git directory or within our own cache for that directory.' Governing rule for both modes; relayed to the implementing agent.
2026-11-18 owner (chat): 'when we're browsing main or a main branch (whether it's the mirrored main branch or the actual local file), a local folder is like a mirror in all cases, or it can be, as the most simple version. It also has the true working directory, as we may wish to have additional features like local modified files and so on only activate for folder mode.' Model: folder mode = mirror behavior for every ref (current branch included, as a committed revision) + a separate working-directory view where folder-only features live.
2026-11-18 origin: this implements bead mb-itzy (recorded 2026-11-07: 'Files should make both a live working tree and read-only cached branch snapshots accessible'). The model it builds is docs/project/architecture/arch-open-modes.md (mb-lsx1, PR #558); mb-itzy now depends on this bead. The title's last clause is stale: the checked-out branch, chosen as a ref, shows its commit, and the Working tree row returns to the live files.
2026-11-18, from PR #558 (docs only; review A, A17). What this change must also do in the documents, since #558 kept every sentence that is true on main and only pointed at the design:

Requirement sharpened by review A (arch-open-modes.md, Showing a Revision Never Writes the Checkout): nothing changes in the working tree, the Git directory, or the common directory (`git rev-parse --git-dir --git-common-dir`). In a linked worktree a cachetextconv driver wrote refs/notes/textconv/<driver> into the main repository's .git and left the worktree's own directories unchanged (Git 2.50.1), so the fixture needs a linked-worktree case and a snapshot of all three places.

Guide wording to change with the code (replacement text is the design review's, in #558's vocabulary):
- docs/command-line.md, Beside a Checkout, last paragraph: "opens your checkout in folder mode: its working tree, and any branch or tag as a read-only revision".
- docs/browsing-history.md, "A local folder has no switcher…": "A repository folder has the same switcher, with the working tree first. Choosing a branch or tag shows its last commit read-only and checks nothing out." Remove the second half of the "Branches of a local repository" line #558 added to What It Does Not Do Yet.
- docs/design-system.md, Which Kind Each Context Gets: a row for the checkout's selector (local, remote, and tag chips, "checked out" in words, and a Working tree row). test_each_context_assigns_its_chip_kind holds that table to the code.
- With View on branch and Browse code in a repository folder (the follow-up): docs/reviewing-pull-requests.md, Code Controls, and docs/design-system.md, the View on branch paragraph: the head as a revision view, and the working-tree copy as a separate, labelled action. Remove the "pull request's code beside a checkout that is elsewhere" line #558 added to What It Does Not Do Yet.
- "Designed, not built" pointers to turn into present tense: arch-source-sessions-and-pins.md (status line, Subjects, the pin guard, View on branch), arch-mirror-acquisition-and-refresh.md (the source routes), arch-views-models-routes.md (the source-routes row), arch-server-and-content.md (Inert Markdown, Acquired Git Sources), arch-repository-cache.md (Repository Stores), arch-github-pull-requests.md (Browse code and View on branch), plan-2026-11-10-native-macos-app.md (the identity bullet), and in arch-open-modes.md the "Not built" notes under Views and Pull Requests in a Repository Folder and this bead's row in Implementation Status.
- This branch conflicts with #558 in arch-source-sessions-and-pins.md and arch-views-models-routes.md (documents only).
