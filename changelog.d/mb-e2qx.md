- `GET /api/plugin/github/gh-requests` reports what the servers sharing the event log
  asked of GitHub over a window, an hour by default: the `gh` calls for every call, for
  each budget they were charged to (a reader’s own action, automatic, speculative, and
  the cores walk), and for each job they ran in, with the HTTP statuses GitHub answered,
  the `core` calls and GraphQL points spent, the share answered `304`, `gh`’s median and
  95th percentile time, the calls that repeated an identical one, how many ran at once
  over time, and how long their jobs waited for a network slot; and what the log does
  not hold, such as when a page first showed GitHub’s answer.
  `metab <folder> --api '/api/plugin/github/gh-requests?since=...&pid=...'` prints it
  ([GitHub Requests](docs/realtime-debugging.md#github-requests)).

- Each `gh` call’s record in the event log now says the HTTP status GitHub answered and
  what the answer cost, the budget the call was charged to, and a fingerprint that is
  the same for two calls that ask GitHub the same thing, and its duration is `gh`’s
  alone, without reading the answer.
  A job’s `queued_ms` now counts every wait for a network slot, including those of a
  scan that takes a slot for each page
  ([The Request Report](docs/project/architecture/arch-github-pull-requests.md#the-request-report)).
