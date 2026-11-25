- The agent skill covers a whole stack’s guided review end to end: it finds a stack and
  its top layer from the repository’s URL, refreshes the list of stacks when a new one
  is missing, says which layers change each file so a step cites the right one, picks
  and tests ranges from the comparison’s own lines without a checkout, and hands the
  user the stack’s page, which `--present` cannot name.
  It and [Working With Agents](docs/working-with-agents.md) list the `/stack/<s>`
  addresses.
