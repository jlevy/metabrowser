- A pull request’s refresh now also reads its operational status from GitHub with one
  GraphQL query: whether it conflicts, GitHub’s merge verdict, its review decision, its
  checks with whether each is required, auto-merge, and the merge queue.
  The status is kept beside the record, never in it, so a check that finishes changes no
  record, catalog row, or core.
  The pull envelope (`/api/plugin/github/pull`) answers it as `status`, the head’s
  checks as `checks`, and the verdict on them as `readiness`, such as Ready to merge,
  Merge conflicts, Checks failing, or Checks pending, with one requirement for each row
  of GitHub’s merge box; a closed or merged pull request has no verdict.
  `metab <pull request> --show /pull/<n>/checks` prints the verdict and each
  requirement’s status.
  A status read that fails leaves the record and the status read before it, and the
  envelope names why as `status_unavailable`
  ([Operational Status](docs/project/architecture/arch-github-pull-requests.md#operational-status)).

- The repository’s pull-request catalog gains a table for those statuses, so a catalog
  an older Metabrowser wrote is replaced and its list read again once, and an older
  Metabrowser sharing the cache leaves a newer catalog as it is and says to upgrade.
