# Publishing

MetaBrowser versions come from Git tags.
Publishing is performed by the `publish.yml` workflow with PyPI trusted publishing; no
long-lived PyPI token belongs in the repository.

## First-Time PyPI Setup

Create a pending trusted publisher for:

- PyPI project: `metabrowser`;
- GitHub owner: `jlevy`;
- GitHub repository: `metabrowser`;
- workflow: `publish.yml`;
- environment: `pypi`.

The repository must be public before the first trusted-publisher release if required by
the selected PyPI configuration.
Confirm the repository’s public-hygiene gate is green before changing visibility.

## Release Checklist

1. Update local `main` and confirm the worktree is clean.

2. Run the complete gate:

   ```shell
   make verify
   ```

3. Confirm CI is green for the exact commit to be tagged.

4. Review changes since the previous release and choose a semantic version.

5. Create a GitHub release with a `vX.Y.Z` tag.
   The workflow checks out that exact tag, rejects non-semantic tags, and verifies that
   the derived package version matches before publishing.

6. Watch the `Publish to PyPI` workflow through completion.

7. Verify the published metadata and files on PyPI.

8. Run an isolated smoke test against the released version:

   ```shell
   uvx --from metabrowser==X.Y.Z metab --help
   uvx --from metabrowser==X.Y.Z metabrowser --help
   ```

For the first release, the intended tag and package version are `v0.1.0` and `0.1.0`.

## Release Notes

Describe user-visible changes, compatibility notes, and important fixes.
Include a concrete compare link between the previous and new tags.
Do not include private issue identifiers, private repository links, local paths, or
unreleased consumer details.

## Failure Handling

PyPI releases are immutable.
If publication succeeds with a defective artifact, fix the defect and publish a new
patch version; do not delete and reuse the version.

If the workflow fails before publication, fix the workflow or trusted-publisher
configuration on a branch, rerun `make verify`, and create the release only from the
validated commit.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
