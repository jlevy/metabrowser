- The macOS app keeps one mirror per GitHub repository.
  A pull request, branch, commit, folder, or file link, whether sent to the app or
  entered in File > Open URL…, opens the repository on its default branch and goes to
  the link’s page. A second link into the same repository opens in that window and its
  running server instead of starting the server again on the new link: the mirror
  refreshes, a pull request or a commit opens at its page, and a link to another branch
  switches the window to it.
  See [GitHub Links](docs/project/architecture/arch-macos-app.md#github-links).

- `POST /api/source/link` with `{"link": "<URL>"}` opens a link into the repository a
  mirror serves: it starts a refresh, switches the pin where the link names another
  revision, and answers the page to go to.
  `metab URL --api /api/source/link --data FILE` asks it from a terminal.

- **App contract:** The macOS app posts every link into a repository to
  `POST /api/source/link` on the repository’s server, reading `href` and `code`, and
  reads `refreshing` from `/api/source/status` while a link the mirror lacks waits for
  its refresh, where it read `ref_name` and `selection_state`. A repository’s server is
  started on the repository’s address, never on a link.
  `metab` 0.13.0 is the first release with the route.
