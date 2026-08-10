# Supply-Chain Security

Dependencies and build tools are code execution boundaries.
Review this document before adding, upgrading, or invoking a package.

## Required Defaults

- Use uv for Python resolution, execution, and tools.
  Do not use raw `pip` or an activated virtual environment.
- Apply a 14-day release cool-off with `uv.toml`, `UV_EXCLUDE_NEWER`, or the equivalent
  explicit uv flag.
- Commit `uv.lock`, install it with `uv --config-file uv.toml sync --locked` so lock
  drift fails the build, and execute commands with
  `uv --config-file uv.toml run --frozen` so they cannot resolve dependencies.
- Commit `package-lock.json`, use exact JavaScript tool versions, and install it with
  `npm ci`.
- Run locked JavaScript tools with `npx --no-install`; use exact versions for one-shot
  `uvx` tools.
- Disable npm lifecycle scripts unless a reviewed package specifically requires them.
- Keep npm’s release-age gate, exact-save behavior, and lockfile generation enabled.
- Use npm 11.10 or newer so `min-release-age` is enforced rather than ignored.
- Pin GitHub Actions to reviewed full commit SHAs.
- Pin the CI and publishing Node release instead of resolving a moving major version.
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

Three exact releases are exempt from the ordinary cool-off.
All three are published from repositories under this project’s own control, which is the
entire basis for the exemption: the cool-off exists to catch a compromised upstream
publisher, and a first-party release has a known one.

Every exemption is reviewed against its predecessor, and each review confirms the same
three things — the lock delta touches only that package, no runtime dependency was
added, and the published artifact’s SHA-256 matches the digest recorded in `uv.lock`.

| Package | Reviewed against | Notes |
| --- | --- | --- |
| `kpress==0.3.2` | `0.3.1` | CSS-only; no public surface changed |
| `flowmark-rs==0.3.2` | `0.3.1` | Formatting output unchanged |
| `get-tbd==0.4.2` | — | Issue tracker; not a build or runtime input |

npm has no per-package cool-off exclusion, so the tbd session hooks pass
`--min-release-age=0` on their exact pinned `npx --yes get-tbd@0.4.2` invocation.
That version string also appears in the copied agent-skill instructions, where it is
operator-invoked documentation — no build, hook, CI, test, or publishing path runs it.

The exceptions are package-scoped in configuration and do not weaken the global gate.
Changing any of these versions requires a new review against the checks above.

## Verification

`devtools/check_supply_chain.py` checks only safeguards that span configuration files:
npm safety settings, exact direct npm specifications, npm registry and integrity data,
the uv cool-off, matching nvm and fnm versions, full-SHA action references, and trusted
publishing controls.

The configuration files own dependency versions, build behavior, lint and type ratchets,
workflows, and documentation.
`make verify` installs both locks, runs the configured linters and type checkers,
executes the tests and audits, builds the package, inspects its contents, and exercises
the installed wheel and plugin surface.

CI and publishing also run `npm audit --audit-level=moderate` after installing the exact
lock.

Treat an unexpected lockfile source, install script, binary artifact, or publish-time
change as a blocker until it is explained and reviewed.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
