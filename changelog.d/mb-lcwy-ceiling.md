- Each Metabrowser server now keeps its own automatic GitHub work under 300 calls an
  hour, counted from what it spends itself, so several servers on one account leave room
  for the reader’s other tools.
  Past that, until the hour rolls, it checks for changes every minute and a half, reads
  in full every five minutes, and prepares nothing in the background; a reader’s own
  Refresh, Reload, or Fetch is never counted or held.
  `GET /api/plugin/github/pulls-prefetch` reports the ceiling and the hour’s use under
  `governor.ceiling`. See
  [The Provider Boundary](docs/project/architecture/arch-github-pull-requests.md#the-provider-boundary).
