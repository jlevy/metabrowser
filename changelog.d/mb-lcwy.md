- A change to any pull request now reaches a visible Pulls tab within seconds, where it
  waited for the next scan, up to a minute.
  While the tab or a pull request page is visible, the server asks GitHub what was
  updated last with a conditional request, which GitHub answers without counting it
  against the rate limit when nothing changed, and scans the list only when something
  did, and every minute or two regardless.
  The list’s envelope gains `probe_every_s` and `checked_at`. See
  [The Catalog](docs/project/architecture/arch-github-pull-requests.md#the-catalog).
