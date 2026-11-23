- Each Metabrowser server now keeps its own automatic GitHub work under 300 calls an
  hour, counted from what it spends itself, so several servers on one account leave room
  for the reader’s other tools.
  Past that, until the hour rolls, it checks for changes every minute and a half, reads
  in full every five minutes, and prepares nothing in the background; a reader’s own
  Refresh, Reload, or Fetch is never counted or held.
  Work nobody is looking at, the prefetch of records and changed-files lists, the
  catalog’s backfill, descriptions for rows not on screen, and the label set, may spend
  only a third of those calls, so what is on screen keeps the rest: the prefetch now
  reads at most 12 records and 20 files lists from GitHub an hour, where it read 40 and
  100\. `GET /api/plugin/github/pulls-prefetch` reports the ceiling, that share, and the
  hour’s use of each under `governor.ceiling`. See
  [The Provider Boundary](docs/project/architecture/arch-github-pull-requests.md#the-provider-boundary).
