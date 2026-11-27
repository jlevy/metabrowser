- **Link cards on every page.** A Markdown document’s links to files and folders, and
  its links to other sites, now have their link cards in a folder with no GitHub
  identity too, and so do a commit message’s links in a repository without one.
  The card’s code loads when the pointer first rests on a link, so a page no longer
  waits for it to show its links, and that first card still comes up on time.

- **An outside link’s card names where the browser goes.** Its address is read against
  the page’s own, as the browser follows the link, so an address that opens a file
  beside the document, as `http:example.com` does on the local server, has no card and
  keeps its author’s title, as does an address too long to read.

- **For plugin authors:**
  `metabrowser.previewLink(root, anchor, target, { authorTitle })` gives a link in
  authored text its link card on any page, and `forgetPreview` and `disposePreviews`
  take cards away ([Data and Navigation](docs/plugins.md#data-and-navigation)).

- **A link to the served folder’s root names it as its view header does.** Its link card
  names the folder by its own name, on a plain folder too and on a checkout cloned under
  a folder name of its own, as a worktree is, rather than by the repository’s.
