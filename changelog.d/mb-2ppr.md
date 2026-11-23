- An open pull request page’s change checks no longer spend rate limit when something
  else in the repository changes.
  They read the pull request’s issue, whose answer changes only when the pull request
  does, where the pull request’s own answer changed with every push to any branch and
  every issue opened or closed.
  A mergeability GitHub recomputes with nothing else changed now shows at the next full
  read, within a minute or two.
  See
  [Serving Pull Requests](docs/project/architecture/arch-github-pull-requests.md#serving-pull-requests).
