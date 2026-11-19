- The branch and tag chooser lists every branch, tag, and remote branch.
  It showed the first 100 and said “filter to narrow” for the rest.
  Each list is now newest first, by the date of each one’s last commit, which its row
  shows as an age: branches listed by name before, and tags by when they were tagged.
  A mirror’s default branch, or the branch a checkout has checked out, still lists
  first. The list draws only the rows near its view, so scrolling and the arrow keys cost
  the same over ten thousand branches as over a thousand.
  Asking again for a list whose refs have not moved runs no Git, except for a list of
  more than about 9,000 refs, or from a repository with too many unpacked refs to check
  cheaply: those run Git each time.
  For API callers, `GET /api/source/refs` takes no `limit` and answers no `limit`,
  `total`, or `truncated`.
