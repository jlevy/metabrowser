---
type: is
id: is-01m0nefwdtdezh3cja4vyx54c3
title: Nav heading shows the folder name; file header shows the full path with a dimmed prefix
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T19:17:18.906Z
updated_at: 2026-08-22T19:17:18.906Z
---
Follows the wordmark move (sibling bead) -- do that first, since both change the same header.

Nav panel. .header-path currently renders the whole served path, so a deep root spends the panel's width on directories nobody is navigating. Show the final path component only: 'foo', not '/User/levy/wrk/foo'. It stays the main clickable heading with its present jump-to-root behaviour, and the full path belongs in its title attribute so it is still recoverable on hover.

Main view. There is room here, so the file header carries the whole address:

    /User/levy/wrk/foo /              on a folder (Overview)
    /User/levy/wrk/foo / README.md    on a file

The prefix /User/levy/wrk/foo is dimmed. The separating / and every component after it are clickable: the first / keeps exactly the behaviour the root crumb has today, each intermediate directory navigates to that directory, and the filename itself is clickable too -- a no-op when you are already on it, but the row should not have one dead segment in the middle of a run of live ones.

The folder case already has most of this: app.js builds .file-header-path.folder-breadcrumb from rootCrumb plus crumbs joined by .folder-crumb-sep. What changes is that the served-root prefix is rendered dimmed rather than as a single crumb, and that the file case grows the same treatment instead of showing a bare filename.

Truncation needs a decision: a long path plus a long filename will overflow. Dim-prefix-first suggests eliding the middle of the prefix and never the filename.
