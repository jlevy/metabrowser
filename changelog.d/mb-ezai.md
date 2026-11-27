- **Link cards on every page.** A Markdown document’s links to files and folders, and
  its links to other sites, now have their link cards in a folder with no GitHub
  identity too, and so do a commit message’s links in a repository without one.
  The card’s code loads when the pointer first rests on a link, so a page no longer
  waits for it to show its links, and that first card still comes up on time.

- **For plugin authors:**
  `metabrowser.previewLink(root, anchor, target, { authorTitle })` gives a link in
  authored text its link card on any page, and `forgetPreview` and `disposePreviews`
  take cards away ([Data and Navigation](docs/plugins.md#data-and-navigation)).
