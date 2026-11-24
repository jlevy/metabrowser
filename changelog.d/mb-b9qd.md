- An out-of-date guided review stays readable after a push, a rebase, or a force push:
  its steps show the diff at the pull request’s current head, under one warning that
  steps marked changed may not match it, and that its author can update the guide.
  A step that cites a file changed since is marked “changed” in the step list and on the
  step. When none of the files it cites changed, as after merging the base branch in, a
  quiet line says so instead, and the `guided-review` route keeps the commits, pins, and
  paths for agents ([Guided Review](docs/reviewing-pull-requests.md#guided-review)).
