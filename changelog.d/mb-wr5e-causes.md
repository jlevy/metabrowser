- A failed GitHub refresh now says what actually went wrong, such as “GitHub could not
  be reached because the connection to api.github.com at 20.172.24.160 timed out; other
  sites are reachable” or “GitHub answered HTTP 503”, in place of “gh could not reach
  api.github.com”. When `gh` gives up with no answer, Metabrowser checks the network
  itself, resolving `api.github.com` and connecting to each address (through the proxy
  `gh` would use), to tell an unreachable GitHub from a slow one; on macOS, when GitHub
  cannot be reached and no proxy is set, it also opens one connection to
  `captive.apple.com`, the host macOS checks for a working network, to say whether other
  sites are reachable.
  `METABROWSER_NETWORK_PROBE_CONTROL=0` turns that connection off, and
  `METABROWSER_NETWORK_PROBE=0` the whole check.
  A repeated failure says how many calls to GitHub failed in the last hour, and
  `metab . --api /api/event-log/failures` lists recent failures by cause; see
  [GitHub Failures](docs/realtime-debugging.md#github-failures).
