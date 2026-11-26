- Refresh is now one circular-arrow icon at the top of the navigation pane, just before
  the Metabrowser menu’s gear, on every page and under every tab, where the Pulls
  toolbar’s text button was.
  One press refreshes everything the page shows, what is on screen first: the open pull
  request page or file and the tab in front, then the other tabs, so a tab you turn to
  next is already fresh.
  For a repository opened by its URL, or a branch or tag of a checkout whose origin
  Metabrowser keeps a store of, it fetches from the origin first; on a checkout’s
  working tree it reads the files and history again without a fetch.
  It dims while what is on screen refreshes, and its key is `1` under every tab, so the
  Files filters and the Pulls state chips now start at `2`.
- The “Fetched 3 min ago” line at the foot of the navigation pane is no longer a button:
  Refresh at the top is the one way to fetch again
  ([Refresh, Retry, and Reload Page](docs/design-system.md#refresh-retry-and-reload-page)).
