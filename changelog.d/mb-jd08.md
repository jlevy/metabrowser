- An open pull request page’s change checks no longer send the whole pull request back
  every few seconds. The page names the record it shows, and the server’s answer leaves
  that record out when nothing replaced it, which for a long conversation was a third of
  a megabyte each time.
  `POST /api/plugin/github/pull-refresh` accepts `"held"`, a `record_revision`, and then
  answers `record_held` in place of `record` for that record.
  See
  [Serving Pull Requests](docs/project/architecture/arch-github-pull-requests.md#serving-pull-requests).
