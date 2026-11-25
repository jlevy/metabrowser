- **A guided review’s step can cite past its pull request.** Besides a file the pull
  request changes, a reference can be another pull request, `{pull: 811}`, a file as
  another pull request changes it, `{pull: 811, path: docs/plan.md}`, or a commit,
  `{commit: "<full commit ID>"}`, so a layer of a stack can point at its neighbors.
  A pull request shows as a row with its state, title, and place in its stack, and opens
  it; another pull request’s file is drawn as a file of this one is, from that pull
  request’s own changes, and its **Open full diff** opens it there; a commit shows as a
  row of its subject, when it was made, and its short ID. Each is read from what is
  already cached, and none makes a guide out of date
  ([Guided Review](docs/reviewing-pull-requests.md#guided-review)).

- **Plugin routes:** each reference in a `GET /api/plugin/github/guided-review` answer
  names its `kind`, `file`, `pull_file`, `pull`, or `commit`, and carries `pull`,
  `commit`, `comparison`, and `target` beside its other fields, null where its kind has
  none: a `pull_file`’s `comparison` is its pull request’s pins and routes, and a
  `pull`’s or a `commit`’s `target` is what its row names.
  The `Collection/v1` schema accepts the three new kinds and refuses a range in another
  pull request’s file and a commit cited beside anything else
  ([Collection Format](docs/project/architecture/arch-collection-format.md#the-record)).
