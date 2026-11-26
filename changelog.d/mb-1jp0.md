- **A Markdown file too large to show rendered no longer holds up the files after it.**
  In a pull request’s Changes, a document whose two sides are over the rendered view’s
  size limit is now refused from the sizes alone, before either side is read.
  Reading a 566 KB document’s sides first took 260 to 380 ms on a loaded machine, and
  the next file’s rendered view waited behind it.

- **The request log says where a rendered diff’s time went.** A pull request’s
  rendered-diff request now records the time it waited for the projection slot
  (`queue`), for the Markdown process to start (`start`), for the comparison (`read`),
  and for the projection (`render`), in `Server-Timing` and the event log.
  The Markdown process’s start is its own event-log job.
