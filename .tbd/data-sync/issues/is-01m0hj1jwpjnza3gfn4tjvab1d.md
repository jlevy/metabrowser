---
type: is
id: is-01m0hj1jwpjnza3gfn4tjvab1d
title: Filtered nav lists folders whose subtree has no matches
kind: bug
status: closed
priority: 0
version: 3
assignee: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-08-21T07:02:26.964Z
updated_at: 2026-08-21T07:42:03.989Z
closed_at: 2026-08-21T07:42:03.988Z
close_reason: A directory is listed only when its subtree holds a match. The collapsed-folders note is gone with the design that needed it.
---
With a filter on, the nav tree lists folders whose entire subtree matches nothing.

Reproduced with the Media preset on this repository: the root shows `devtools`, `docs`, `skills`, `src` and `tests`, and none of `devtools`, `docs`, `skills` or `src` contains a single media file. Expanding into them shows more of the same: `src/metabrowser` lists all eight of its subfolders, `src/metabrowser/builtin_plugins` lists all eight plugin folders.

Cause: `applyTreeFilters` (static/app.js) can only judge rows that are in the DOM. For a folder with no loaded children it takes the honest-but-wrong-for-the-user branch:

    // Nothing loaded under it: the filter cannot speak for this
    // subtree, so the folder stays and gets counted.
    unloadedFolders += 1;

Every collapsed folder and every lazy stub past the server depth cap therefore survives the filter. The footnote it drives ("N collapsed folders may contain additional matches") counts up rather than down as you expand: 48 at the root, 65 after opening `src/metabrowser`.

Two smaller faults in the same branch:
- A folder the server already reported empty has had its `.tree-children` removed by `markFolderKnownEmpty`, so it also lands in the "unknown, keep it" branch even though it is known to hold nothing.
- The same branch inflates the footnote count with those known-empty folders.

Wanted: a folder appears under a filter only when its subtree actually contains a match.
