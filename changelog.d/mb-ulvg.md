- `GET /api/plugin/github/gh-requests` now says how long each `gh` call waited for a
  network slot just before it started, where it said how long the spans the calls ran in
  waited (`queued` counts `waits`, not `spans`); `order`, how many of a less urgent
  lane’s calls started while a more urgent call asked before them waited for a slot or
  ran; `repeats`, each read that repeated an identical one, as `gh api user`; and, in
  `in_flight`, the most spans with a call in flight at once and the most of them holding
  a network slot. Each `gh` call’s record says how long its span had waited for slots as
  it started (`parent_queued_ms`)
  ([The Request Report](docs/project/architecture/arch-github-pull-requests.md#the-request-report)).

- A scripted session of browsing pull requests,
  `explorations/performance-loop/github_browsing.py`, runs against the in-process
  stand-in in `tests/test_github_browsing_benchmark.py`, which holds its request report
  to the merge readiness plan’s invariants, and against a running server with
  `github_browsing.py live --url …`; a live run against this repository is recorded in
  [GitHub Requests While Browsing](explorations/performance-loop/github-requests/README.md).
