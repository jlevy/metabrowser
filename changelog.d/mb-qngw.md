- When the account’s GitHub rate limit runs low, an open pull request page stops
  re-reading the whole pull request every minute or two and keeps only its change
  checks, which cost nothing while nothing changed.
  A change those checks find still shows within seconds, and Refresh still reads at
  once. Prefetching already stopped there.
  See
  [Serving Pull Requests](docs/project/architecture/arch-github-pull-requests.md#serving-pull-requests).
