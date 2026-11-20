- Guided PR is a new tab on a pull request whose description carries a `guided-pr`
  block: an author-provided feature overview, architecture, and ordered review steps
  with excerpts from the pull request’s exact diff.
  The block is the new external format `metabrowser.github:GuidedPR/v1`, versioned by
  its contract ID, and a guide goes out of date when the pull request’s head or merge
  base changes ([Guided PR](docs/reviewing-pull-requests.md#guided-pr)). First
  contributed in #599.
