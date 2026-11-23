- A page of a mirror on a branch now shows a push within seconds.
  While the page is visible, the server asks the origin every few seconds
  (`STORE_PROBE_S`) where that branch is, with one `git ls-remote` of the branch, and
  fetches at once when it moved; before, a push waited for the freshness window and the
  page’s next poll. The whole mirror is fetched once a freshness window while a page on a
  branch is visible, and a hidden page asks for nothing.
  That fetch, like the one a server runs while no page is visible, is quiet: the
  freshness row says and announces nothing for it.
  `/api/source/status` gains `probe_every_s` and `refresh_quiet`, and
  `POST /api/source/refresh` takes `{"for": "page"}`, the page’s own ask
  ([Refresh Cadence](docs/project/architecture/arch-mirror-acquisition-and-refresh.md#refresh-cadence)).
