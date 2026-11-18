- Changelog entries for unreleased changes are files under `changelog.d/`, one per
  change, which a release folds into this changelog
  ([changelog.d/README.md](changelog.d/README.md)). A pull request that adds an entry to
  the Unreleased section directly fails `make lint-check`, and
  `python -m devtools.changelog show` prints the Unreleased section with every pending
  entry folded in.
