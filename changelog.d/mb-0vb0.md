- While the Pulls tab is open, Metabrowser reads the operational status of the
  repository’s newest open pull requests, a page of them per GraphQL query: whether each
  conflicts, GitHub’s merge verdict, its review decision, its checks rolled up,
  auto-merge, and the merge queue.
  The tab’s own refresh ask starts it when the list changed, when a fetch moved a base
  branch they target since the last scan, and otherwise periodically, and reads answers
  GitHub had not finished computing once more a little later.
  `GET /api/plugin/github/pull-statuses?numbers=<n>,...` answers each named pull
  request’s status and verdict from the cache, or why it has none, and how the last scan
  ended; `metab <repository> --api '/api/plugin/github/pull-statuses?numbers=...'`
  prints it
  ([Operational Status](docs/project/architecture/arch-github-pull-requests.md#operational-status)).
  A pull request the last scan did not read, one past the newest it reads or no longer
  open, has no verdict from an older scan: it is answered `not_scanned`; one whose
  status was observed against another base than its row’s, before a retarget was read,
  is answered `other_base`.

- A pull request page shows its checks only beside the status that counts them: after
  the Pulls tab’s scan sees a new head, a new base, or checks that moved, the page reads
  its own status and checks at once, and meanwhile shows the scan’s verdict with no list
  of another head’s checks.
