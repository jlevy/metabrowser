- After GitHub’s rate limit lifted, a Pulls tab whose descriptions of rows not on screen
  were still held, by the background’s share of the hour or by the catalog’s first fill,
  asked its server again every second for as long as the hold lasted, rather than
  backing off as it does for any other hold.
  It now backs off, and waits for a rate limit’s reset only while the reset is still
  ahead. Each of those asks was answered locally and cost GitHub nothing.
