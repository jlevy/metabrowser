- Every page that github.com has a page for has one **View on GitHub** button in its
  header’s upper right: a file, a folder, the served root, each of a pull request’s
  tabs, and a commit’s page.
  It opens the page on github.com in a new tab, and its chevron’s menu offers **Copy
  Link** and **Open in Browser**; the arrow keys, Home, End, Escape, and Tab work in the
  menu. A file or folder links to the version `origin` has, as of your last fetch: at
  your commit once it is pushed, and before then at the commit your branch last shared
  with its upstream branch, or with `origin`’s default branch.
  A file with local edits links to its pushed version; a file only your unpushed commits
  hold, a staged file in no commit, an untracked or ignored file, and a deleted one have
  no button. The button replaces the View on GitHub link among a pull request’s dates.
  See [View on GitHub](docs/design-system.md#view-on-github).

- `metab --api '/api/counterpart?page=<page>'` answers a page’s github.com counterpart,
  or why it has none, and plugins can draw the same button with `mountCounterpart` and
  `counterpartButton`
  ([Rendering and Formatting](docs/plugins.md#rendering-and-formatting)).
