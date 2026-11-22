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

4. Review changes since the previous release, choose a semantic version
   ([Choosing a Version](#choosing-a-version)), and assemble the changelog in the
   release-preparation pull request:

   ```shell
   uv --config-file uv.toml run --frozen python -m devtools.changelog assemble
   ```

   It writes every fragment in `changelog.d/` at the top of `CHANGELOG.md`’s Unreleased
   section, the most recently landed first, and deletes the fragments.
   Then add a `## X.Y.Z` heading right below the Unreleased section’s note, so the
   entries fall under the version and Unreleased keeps only its note.
   The changelog check in `make lint-check` lets this pull request through, because the
   entries it adds come from the fragments it deletes.

5. Once that lands, confirm CI is green for the exact commit to be tagged and record its
   full SHA as `RELEASE_COMMIT`. Confirm that the commit holds no fragment, which this
   command shows by listing only `changelog.d/README.md`:

   ```shell
   git ls-tree --name-only "$RELEASE_COMMIT" changelog.d/
   ```

6. After approval of the exact commit and notes, check the version tag as described
   above and create a GitHub release with a `vX.Y.Z` tag targeting `RELEASE_COMMIT`.
   Verify that the resulting tag resolves to the approved commit.
   The workflow checks out that exact tag, rejects non-semantic tags, and verifies that
   the derived package version matches before publishing.
   Its job runs only for a tag that starts with `v`, so a release of the macOS app,
   tagged `macos-v<version>` ([macOS App Releases](#macos-app-releases)), never reaches
   PyPI.

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
The macOS app releases on its own, under its own tags, with the
[App Release Checklist](#app-release-checklist).

## Choosing a Version

Versions are semantic, `X.Y.Z`. The macOS app’s contract with `metab` is at the minor
release, as the owner set on 2026-11-18; this section is where that rule is written.

- **A change the app depends on is a new minor or major release, never a patch.** That
  is any change to what the app reads from `metab`: a flag, route, JSON field, output
  line, or exit status.
  [The app’s contract](project/architecture/arch-app-contract.md) declares all of it,
  and its checks make a branch name such a change in the changelog and fail a patch
  release that holds one
  ([Versioning](project/architecture/arch-app-contract.md#versioning)). The app’s
  minimum, `MetabRequirement.minimumRelease` in
  `apps/macos/Sources/ShellCore/Setup/MetabVersion.swift`, names that release as
  `X.Y.0`.
- **A bug fix that keeps what the app reads may be a patch.**

The reason: a patch is then always safe for an app already in use, and a checkout’s
development version lines up with the minimum.
A checkout reports the next minor release as its development version (`bump` in
`pyproject.toml`) and rebuilds that version after each commit or tag (`cache-keys` in
its `[tool.uv]`), so after `make install` it meets a minimum raised to that release.

To raise the minimum, name the next minor release after the latest one, since no
checkout reports a newer one, and leave `MetabRequirement.isReleased` false until that
release is on PyPI, so the app can accurately report whether its runtime is available.
Update the [README’s preview requirement](../README.md#developer-preview) and
[release status](installation.md#release-status) at the same time.
`tests/test_macos_app_pins.py` checks the form, both bounds, the bump, and the cache
keys.

Proposed and not yet decided by the owner
([Owner Decisions](project/specs/active/plan-2026-11-18-cli-dependencies-and-doctor.md#owner-decisions)):

- **Before 1.0**, the minor release is the boundary in both directions: a `0.Y.0` may
  add what the app needs and may change what an older app read, and its notes say so.
- **From 1.0**, a change that removes or alters what a released app reads is a major
  release, and one that only adds what a newer app needs is a minor release.
- **A fix the app cannot work without** ships as a minor release, so the minimum stays
  `X.Y.0`.

## macOS App Releases

The native app is released on its own, under `macos-v<version>` tags, as a draft release
that the owner publishes ([apps/macos/README.md](../apps/macos/README.md#each-release)).
Its tag is created on GitHub before the draft, since a draft does not create its tag and
`gh release create --verify-tag` refuses a missing one.
One rule covers every app release:

1. Record the approved, gated full commit SHA as `RELEASE_COMMIT`, as in
   [Agent-Operated Releases](#agent-operated-releases).

2. Check the tag. It must be absent, which this command reports as a 404, or, on a retry
   after a transient failure, already resolve to `RELEASE_COMMIT`, in which case skip
   step 3. Stop if it resolves to any other commit.

   ```shell
   gh api repos/jlevy/metabrowser/git/ref/tags/macos-vX.Y.Z --jq .object.sha
   ```

3. Create the tag at that SHA, then confirm it resolves to `RELEASE_COMMIT`:

   ```shell
   gh api repos/jlevy/metabrowser/git/refs \
     -f ref=refs/tags/macos-vX.Y.Z -f sha="$RELEASE_COMMIT"
   gh api repos/jlevy/metabrowser/git/ref/tags/macos-vX.Y.Z --jq .object.sha
   ```

4. Create the draft on that tag with
   `gh release create macos-vX.Y.Z --draft --verify-tag --latest=false` and the
   release’s assets. For a release built by CI, the release workflow’s `draft` job runs
   this step.

5. After the owner checks the draft’s download and approves the image’s SHA-256 and the
   notes, publish it without making it the Latest release, so the Python package’s
   release stays Latest:

   ```shell
   gh release edit macos-vX.Y.Z --draft=false --latest=false
   gh api repos/jlevy/metabrowser/releases/latest --jq .tag_name   # not macos-vX.Y.Z
   ```

   In the web UI, untick “Set as the latest release” before publishing.

Never push a tag from a clone: session git credentials are branch-scoped, and the API
call takes the approved SHA itself, so nothing local resolves it.
The agent runs these commands once the owner has approved `RELEASE_COMMIT`, as it
creates the Python package’s tag; the owner decided that on November 17, 2026 (Q8 of the
[macOS publishing plan](project/specs/active/plan-2026-11-16-macos-app-publishing.md#open-questions)).

### App Release Checklist

The app’s releases follow
[the release runbook](../apps/macos/README.md#building-a-release), whose steps this
checklist names in order; the runbook has the commands.

1. The owner’s setup is done: `make macos-signing-check` on the build Mac reports
   nothing missing, and O5’s repository settings are on.
2. The `metab` release that `MetabRequirement.minimumRelease` names is published and
   verified on PyPI, and the commit that sets `MetabRequirement.isReleased` to true is
   on `main`. The version change is on `main` after it, and the owner approved
   `RELEASE_COMMIT`, which contains both.
3. The tag is created at `RELEASE_COMMIT`, as above.
4. The owner unlocked the release keychain, and `make macos-release` built, signed,
   notarized, and checked the image; the owner locked the keychain again.
5. The draft holds the image and its checksum, with the notes, not as Latest.
6. `make macos-check-release` with `BUILT=local` and `EXPECTED_TEAM_ID` passes on the
   draft, and passes with `LAUNCH=1` at the Mac.
7. The owner opened the draft’s download on a Mac or VM that has not run the app.
8. The owner approved the image’s SHA-256 and the notes; the draft is published with
   `--latest=false`, and the check passes again on the published release.
9. The release’s approval record holds what the runbook lists.

## Release Notes

Describe user-visible changes, compatibility notes, and important fixes.
Include a concrete compare link between the previous and new tags.
Do not include private issue identifiers, private repository links, local paths, or
unreleased consumer details.

## Failure Handling

Treat a version as spent once its tag exists.
PyPI releases are immutable.
With immutable releases on, GitHub enforces the same for published releases: their tag
“cannot be deleted while the release exists”, and once the release is deleted its tag
name cannot be reused
([Immutable releases](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases)).
The
[macOS publishing plan](project/specs/active/plan-2026-11-16-macos-app-publishing.md)
has the owner turn them on before the app’s first release (its step O5), with a tag
ruleset that stops `v*` and `macos-v*` tags being moved or deleted.

- If publication succeeds with a defective artifact, on PyPI or in an app release, fix
  the defect and publish a new patch version; do not delete and reuse the version.
- If `publish.yml` fails for a transient reason, such as a network error or an outage,
  or because of the trusted-publisher configuration on PyPI, fix that configuration if
  needed and re-run the failed run, which checks out the same tag.
- If it fails for a reason that needs a change to the code or the workflow, fix it on a
  branch, rerun `make verify`, and release the next patch version from the validated
  commit. A run takes its workflow from the tagged commit, so the existing tag cannot
  pick up the fix. The spent version’s GitHub release stays, with no package on PyPI
  behind it: edit its notes, which stay editable, to say it was not published and to
  name the replacement version.
- The macOS app follows the same rule from the moment its `macos-v*` tag exists, which
  is before anything is signed: a transient failure, such as a notary timeout, is
  retried at the same tag, and a failure that needs a change, such as a rejected
  notarization or a draft that fails its check, is fixed in a new commit released under
  the next version.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
