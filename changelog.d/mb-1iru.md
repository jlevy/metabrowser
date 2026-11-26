- The Checks tab now classifies each check as GitHub does, from the pull request’s
  status read: a cancelled check is muted, and a stale one or one that failed to start
  is pending, as `gh pr checks` marks them.
  Its checks are listed failing first, then pending, then the rest, under GitHub’s
  summary of them, such as “Some checks are still pending”, and its last line says in
  GitHub’s words whether the pull request conflicts with its base.

- A check that finishes no longer re-renders a pull request’s conversation: the record
  no longer holds its check runs, commit statuses, or mergeability, which are its
  operational status, kept beside it.
  A change a probe finds in them reads the status alone, with one GraphQL query and no
  REST read of the record, and a full refresh asks GitHub two fewer REST requests.
  A page whose record has no status of its head, as a prefetched one has, reads one.
  Records and cores an older Metabrowser cached are read again once.
  The pull envelope’s `record` drops `pull.mergeable`, `check_runs`, `status`, and their
  `truncated` and `unavailable` parts, and `metab <pull request> --show /pull/<n>`
  prints `checks=pass:2,pending:1` by GitHub’s buckets in place of `check_runs=` and
  `statuses=`
  ([Operational Status](docs/project/architecture/arch-github-pull-requests.md#operational-status)).
