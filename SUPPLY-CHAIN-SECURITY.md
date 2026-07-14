# Supply-Chain Security

Dependencies and build tools are code execution boundaries.
Review this document before adding, upgrading, or invoking a package.

## Required Defaults

- Use uv for Python resolution, execution, and tools.
  Do not use raw `pip` or an activated virtual environment.
- Apply a 14-day release cool-off with `uv.toml`, `UV_EXCLUDE_NEWER`, or the equivalent
  explicit uv flag.
- Commit `uv.lock` and install it with `--frozen` in CI and publishing workflows.
- Use exact versions for one-shot `uvx` and `npx` tools.
- Disable npm lifecycle scripts unless a reviewed package specifically requires them.
- Keep npm’s release-age gate, exact-save behavior, and lockfile generation enabled.
- Pin GitHub Actions to reviewed full commit SHAs.
- Build without isolated dependency re-resolution and test the wheel in a clean
  environment.

## Review Before Adding

Confirm:

1. the dependency is necessary and existing code cannot provide the capability;
2. the package name, publisher, source repository, and license are correct;
3. the selected release is at least 14 days old;
4. the release artifacts and install behavior are expected;
5. transitive dependency growth is proportionate;
6. the lockfile change contains no unexplained package or source changes.

## Audited First-Party Exceptions

Two exact first-party releases are exempt from the ordinary cool-off for this release:

- `kpress==0.1.0`, required for the first MetaBrowser release;
- `flowmark-rs==0.3.1`, used to format and verify Markdown.

The exceptions are package-scoped in configuration and do not weaken the global gate.
Changing either version requires a new review and an updated rationale.

## Verification

`devtools/npm_policy.py` checks the repository configuration, exact KPress dependency,
lockfile source, and pinned tool references.
`make lint-check` runs that policy together with public-hygiene, formatting, lint, and
type checks.

Treat an unexpected lockfile source, install script, binary artifact, or publish-time
change as a blocker until it is explained and reviewed.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
