- Checking which GitHub account `gh` is signed in to no longer spends the account’s rate
  limit. Every refresh checks it, twice for a pull request, and each check was a
  `gh auth status` that cost one call; it is now a conditional `gh api user`, which
  GitHub answers without counting it while the account is the same.
  See
  [The Provider Boundary](docs/project/architecture/arch-github-pull-requests.md#the-provider-boundary).
