- An open pull request page’s change checks no longer spend rate limit when something
  else in the repository changes.
  They read the pull request’s issue, whose answer changes only when the pull request
  does, where the pull request’s own answer changed with every push to any branch and
  every issue opened or closed.
  While GitHub is still working out whether a pull request can merge, the page also
  checks the pull request itself for a short while, so “Merge status unknown” still
  resolves within seconds.
  Once GitHub has answered, a later change of that answer with nothing else changed, as
  when the base branch moves, shows at the next full read, within a minute or two.
  See
  [Serving Pull Requests](docs/project/architecture/arch-github-pull-requests.md#serving-pull-requests).
