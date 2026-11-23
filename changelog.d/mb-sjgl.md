- A pull request open in a visible tab now shows a change on GitHub within seconds,
  where it took up to a minute and a half.
  While the page is visible it asks every few seconds, and the server checks the pull
  request with a conditional request, which GitHub answers without counting it against
  the rate limit when nothing changed; it reads the whole pull request again only when
  something did, and every minute or two regardless.
  Pending checks are checked the same way.
  The page’s envelope gains `probe_every_s`, and `verified_by` can be `probe`. See
  [Serving Pull Requests](docs/project/architecture/arch-github-pull-requests.md#serving-pull-requests).
