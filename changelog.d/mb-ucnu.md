- A pull request’s refresh now reads what the requests that started or joined it asked
  for, whichever of them started it.
  A refresh of the source that found only the attended pull request’s checks due no
  longer reads its whole record from GitHub when a rate-limit hold was noted while it
  waited, and a retried commit fetch, a commit the mirror lacks, or a link into the pull
  request reads the record, and so brings its newer head, even when a visible page’s own
  ask joined the same refresh or was refused as one too many just before.
