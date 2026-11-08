# Publishing

Metabrowser versions come from Git tags.
Publishing is performed by the `publish.yml` workflow with PyPI trusted publishing; no
long-lived PyPI token belongs in the repository.

## Agent-Operated Releases

The release process is designed to be operated end to end by a coding agent: the agent
runs the checklist below, lands the release-preparation pull request, creates the GitHub
release, watches the publish workflow, and runs the post-release verification.
The human maintainer’s role is review and the platform entitlements, not manual release
mechanics.

Record the reviewed, gated full commit SHA as `RELEASE_COMMIT` before requesting
approval. Obtain approval for that exact commit and the complete release notes.
A branch name can advance after approval, so use the recorded SHA when creating the
release.

Before publication, confirm the version tag is absent or resolves to that approved
commit. Stop if an existing tag resolves elsewhere; `--target` chooses the commit only
when GitHub creates a new tag.
If any preflight check cannot be completed, do not publish.

The agent creates the approved release with the GitHub CLI:

```shell
gh release create vX.Y.Z --target "$RELEASE_COMMIT" --title vX.Y.Z --notes-file <notes>
```

`.claude/scripts/ensure-gh-cli.sh` installs a checksum-pinned `gh` and authenticates
from the session’s `GH_TOKEN`, which must carry `contents: write`. In proxied remote
sessions, route GitHub hosts directly with `NO_PROXY` before running the script — the
session’s HTTPS relay can intercept GitHub with its own 403 even when the environment’s
egress policy allows it; `gh` honors `NO_PROXY` natively.
Run `tbd shortcut setup-github-cli` for the verified recipe and the diagnostic decision
tree. Session git credentials are branch-scoped, so tags and releases go through `gh`,
never `git push --tags`. A release created this way fires `release: published` normally,
which is what triggers `publish.yml`; do not add `workflow_dispatch` to `publish.yml`
(the supply-chain check rejects it) and do not create releases from workflow
`GITHUB_TOKEN` credentials, whose events do not trigger workflows.

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

3. Compare the candidate with the previous published release using the
   [previous-release performance loop](../explorations/performance-loop/README.md#comparing-a-candidate-with-the-previous-release).
   Record the ranges and verdict in a committed experiment and regenerate the
   performance report. Every candidate run must pass the hard responsiveness and
   correctness gates, and a repeatable wrong-way metric blocks the release until it is
   fixed or explicitly accepted.
   For the first release, record a baseline instead.

   On a machine that has not run the loop before, build the corpus first — it is
   gitignored and machine-local, so a fresh checkout has none:
   [Building the corpus](../explorations/performance-loop/README.md#building-the-corpus).
   Label the runs with the experiment number rather than `release` or `candidate`; a
   label reused from an earlier round pools across corpora, and `compare` will refuse
   it.

   An intended change to a response makes the backend comparison report `valid: false` —
   a schema bump moves `tallies`, and the harness cannot know it was deliberate.
   Read `equivalence`: differing rows is a regression until shown otherwise, and
   differing tallies confined to what the changelog describes is the explicit acceptance
   this step allows.

4. Confirm CI is green for the exact commit to be tagged and record its full SHA as
   `RELEASE_COMMIT`.

5. Review changes since the previous release and choose a semantic version.

6. After approval of the exact commit and notes, check the version tag as described
   above and create a GitHub release with a `vX.Y.Z` tag targeting `RELEASE_COMMIT`.
   Verify that the resulting tag resolves to the approved commit.
   The workflow checks out that exact tag, rejects non-semantic tags, and verifies that
   the derived package version matches before publishing.

7. Watch the `Publish to PyPI` workflow through completion.

8. Verify the published metadata and files on PyPI, including the AGPL license, Python
   classifiers, source and issue links, and release notes.

9. Run isolated smoke tests against the released version.
   As in the [publish workflow](../.github/workflows/publish.yml), exempt only the
   reviewed Metabrowser release from the cool-off and refresh its package metadata on
   each probe. Dependencies retain the configured cool-off.

   ```shell
   release_version=X.Y.Z
   release_bound="$(date -u +%Y-%m-%d)T23:59:59Z"
   uv --config-file uv.toml tool run \
     --refresh-package metabrowser \
     --exclude-newer-package "metabrowser=$release_bound" \
     "metabrowser@$release_version" --help
   uv --config-file uv.toml tool run \
     --refresh-package metabrowser \
     --exclude-newer-package "metabrowser=$release_bound" \
     --from "metabrowser==$release_version" metab --help
   uv --config-file uv.toml tool run \
     --refresh-package metabrowser \
     --exclude-newer-package "metabrowser=$release_bound" \
     --from "metabrowser==$release_version" metabrowser --help
   ```

10. Verify a fresh, project-local installation of the public Agent Skill.
    Review and record an exact `skills` installer version under the
    [supply-chain policy](../SUPPLY-CHAIN-SECURITY.md), then replace the installer
    placeholder below. Pin the skill source separately to the approved `RELEASE_COMMIT`;
    the installer’s
    [command reference](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)
    documents the `owner/repo@ref` syntax for a tag or full commit.

    From the repository, save the approved skill and npm configuration path before
    entering a fresh temporary directory.
    Passing that configuration explicitly keeps npm’s lifecycle-script, release-age and
    engine checks active there:

    ```shell
    SKILLS_INSTALLER_VERSION='<reviewed-exact-version>'
    release_npmrc="$PWD/.npmrc"
    skill_check_dir="$(mktemp -d)"
    git show "${RELEASE_COMMIT}:skills/metabrowser/SKILL.md" \
      > "$skill_check_dir/expected-SKILL.md"
    (
      cd "$skill_check_dir" || exit 1
      npx --userconfig "$release_npmrc" \
        "skills@$SKILLS_INSTALLER_VERSION" add \
        "jlevy/metabrowser@$RELEASE_COMMIT" --skill metabrowser
    )
    ```

    Select project-local installation in that directory when prompted.
    Record the absolute path of its installed `SKILL.md` within that directory as
    `INSTALLED_SKILL`, then verify its bytes:

    ```shell
    cmp "$skill_check_dir/expected-SKILL.md" "$INSTALLED_SKILL"
    ```

    Confirm that the installed skill retains the documented local-`metab` or
    `uvx metabrowser@latest` runner policy.
    Record the installer version, source commit, installed path and comparison result as
    the fresh-install evidence.

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
