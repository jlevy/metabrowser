- The agent skill’s **Write a Guided Review** pins a pull request’s guide to the
  comparison in Metabrowser’s record of it, `.record.comparison.base` and `.head`, which
  the route checks the pins against, rather than to a `git merge-base` of the agent’s
  own, which answers the head itself once a pull request has merged.
  It reads one file’s hunks with `&file=<path>` on a pull request’s or a stack’s
  comparison route, since a comparison answers the hunks of its first few files only and
  marks the rest `deferred`, and says the order a guide is checked in: pin, test each
  range, publish, then read every step through the route and fix what it reports.
  It reads a guide’s outline from the route’s first answer, and each step’s title, note,
  and ranges; narrows a stack’s Documentation files to those a reviewer reads; covers a
  stack whose layers have all merged; and reads a layer’s description from its cached
  record.
