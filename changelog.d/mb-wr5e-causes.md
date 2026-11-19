- A failed GitHub refresh now says what actually went wrong, such as “Couldn’t connect
  to GitHub (api.github.com at 20.172.24.160): the connection timed out; other sites are
  reachable” or “GitHub answered HTTP 503”, in place of “gh could not reach
  api.github.com”. When `gh` gives up with no answer, Metabrowser checks the network
  itself, resolving `api.github.com` and connecting to each address, to tell an
  unreachable GitHub from a slow one.
  A repeated failure says how many calls failed in the last hour, and
  `metab . --api /api/event-log/failures` lists recent failures by cause; see
  [GitHub Failures](docs/realtime-debugging.md#github-failures).
