- The branch and tag chooser of a local checkout has four tabs, **Working tree**,
  **Branches**, **Remotes**, and **Tags**, and opens on the one that holds what the page
  shows. The Working tree tab has one entry, which names the branch your files are on;
  choosing it, or clicking the tab from a branch’s or tag’s page, shows the files on
  disk, and never checks anything out.
  Arrow keys along the tabs only show each tab’s list.
- The row under the Files and Commits tabs is one shape on every page: “Working tree ·
  main” for the files on disk, and the branch, tag, or commit alone for anything else.
  The word “Revision” and the “← Working tree” button are gone.
- A checkout’s row follows its branch: when you, or an agent, check out another branch
  or detach `HEAD` in a terminal, the row and the Working tree tab name it within about
  a second, without a reload.
- **Refresh** on a checkout’s working tree reads your files and history again and then
  fetches the origin in the background, so Remotes and Tags are current; it used to
  fetch nothing there.
  An open chooser list is read again in place
  ([The Ref Selector](docs/design-system.md#the-ref-selector)).
