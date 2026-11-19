- The macOS app’s File > Open URL… now opens a GitHub URL typed without its scheme
  instead of asking for the full URL: `github.com/owner/repo` and
  `//github.com/owner/repo` get `https://`, `http://github.com/…` becomes `https://`,
  and `owner/repo` becomes `https://github.com/owner/repo`. The field shows the full URL
  it checks. Another site’s address, a local path, and an SSH address are still refused.
  `metab github.com/owner/repo` likewise opens `https://github.com/owner/repo` when
  nothing on disk has that name; a folder that does is still served, and `owner/repo`
  alone is still a path.
  See [the app’s guide](docs/macos-app.md#opening-github-links) and
  [What ROOT Names](docs/command-line.md#what-root-names).
