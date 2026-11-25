- The agent skill’s **Write a Guided Review** pins a guide to the comparison the route
  checks: when an agent opens a pull request with its guide, `git merge-base` against
  the fetched base branch and the pushed head, confirmed against Metabrowser’s record of
  it once it opens; for a pull request that exists, or has merged or closed, the
  record’s `.record.comparison.base` and `.head`, since `git merge-base` answers the
  head itself once the base branch holds it.
  It reads one file’s hunks with `&file=<path>` on a pull request’s or a stack’s
  comparison route, since a comparison answers the hunks of its first few files only and
  marks the rest `deferred`, and says the order a guide is checked in: pin, test each
  range, publish, then read every step through the route and fix what it reports.
  It reads a guide’s outline from the route’s first answer, and each step’s title, note,
  and ranges; narrows a stack’s Documentation files to those a reviewer reads; covers a
  stack whose layers have all merged; and reads a layer’s description from its cached
  record, or from GitHub when the record cut it short.
