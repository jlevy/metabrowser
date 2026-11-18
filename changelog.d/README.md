# Changelog Fragments

A change that a user or plugin author can observe writes its changelog entry in a file
of its own here, and a release folds the files into [the changelog](../CHANGELOG.md).

Every pull request used to add its entry at the top of the changelog’s Unreleased
section, so each merge to `main` made every other open pull request conflict there, and
each conflict cost a merge-up and a full CI run.
Git’s `merge=union` driver would resolve those conflicts, but GitHub’s server-side merge
ignores it. A file per change is a file no other pull request touches.

## Writing a Fragment

- **Name it** for the bead that tracks the change, `changelog.d/<bead>.md`, or for a
  short slug in lowercase letters, digits, and hyphens.
- **Write exactly the bullets** that would have gone under Unreleased, in the
  changelog’s style: one or more top-level `- ` bullets, with continuation lines
  indented two spaces and a blank line between bullets.
  Nothing else: no heading, note, or footer.
- **Link from the repository root**, as the changelog does, for example
  `[View Headers](docs/design-system.md#view-headers)`, because the bullets land there
  unchanged. The documentation link check reads a fragment’s links the same way.
- **One change per file.** A later change to something still unreleased edits its
  fragment or adds another.
- **Leave the changelog’s Unreleased section alone.** `make lint-check` fails a branch
  whose Unreleased section gains an entry since it left `origin/main`; correcting an
  entry already there is fine.

`make lint-check` validates the fragments with
`uv --config-file uv.toml run --frozen python -m devtools.changelog check`, and
`... changelog show` prints the Unreleased section with every fragment folded in, which
is what `main` has that the last release lacks.

## At Release

The release-preparation pull request runs `... changelog assemble`, which writes every
fragment’s bullets at the top of Unreleased, the most recently landed first, and deletes
the fragments; the [Release Checklist](../docs/publishing.md#release-checklist) has the
steps around it. `devtools/changelog.py` holds the details.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
