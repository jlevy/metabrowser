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

Packages published from repositories controlled by the `jlevy` project owner are
first-party and exempt from the ordinary cool-off by owner decision.
The table records the exact first-party selections used by this repository.
The delay is waived, but the release review is not: each row still states what changed
or what bounds its blast radius.

Where an exemption upgrades an existing exact release, it is reviewed against its
predecessor, and each review confirms the lock delta, runtime-dependency delta, and the
published artifact’s SHA-256 against `uv.lock`. The review for a new first-party package
records the same evidence for the package and every transitive lock change it
introduces.

| Package | Reviewed against | Notes |
| --- | --- | --- |
| `kpress==0.3.8` | `0.3.6` | Browser assets plus two names in the public CSS contract (0.3.7 and 0.3.8 together): TOC scrollspy without `IntersectionObserver`, over host-rewritten same-document links, and past headings with no layout box; a reload scroll restore confirmed one frame later; the public `--kpress-code-border` and `--kpress-code-radius` tokens; TOC inset and blockquote defaults; `kbd`, `samp`, and link-preview code in the shipped mono face; runtime dependencies unchanged; lock delta is `kpress` alone, wheel SHA-256 `99c32266…f5b0efa9` and sdist `1db5df40…465833bd` match `uv.lock` |
| `kpress==0.3.9` | `0.3.8` | Releases jlevy/kpress#80, which this repository built from commit `5a8e9ae` until KPress released it; the release tree differs from that commit only in `docs/README.md` and the new `docs/releases/0.3.9.md`. It adds the Mermaid diagram renderer and its opt-in controls (`js/diagrams.js`, `js/diagram-controls.js`), their styles and sprite symbols, and the `diagrams` render-request field; runtime dependencies unchanged; lock delta is `kpress` alone, wheel SHA-256 `d3d4cc33…e7ef23f2` and sdist `b15c3e42…a30d09f1` match `uv.lock` |
| `kpress==0.3.10` | `0.3.9` | Releases jlevy/kpress#82, which this repository built from commit `0c0f857` until KPress released it; the release adds the PR’s final-review fixes on top of that commit: the structural box style keeps an ordered or footnote item’s number and applies only to a disabled checkbox (`components.css`), and an `<input>` the sanitizer’s rewrite does not recognize is removed rather than kept (`sanitize.py`). Against `0.3.9` it draws task-list boxes from KPress’s own token (`kpress_task_checkbox`) instead of `mdit-py-plugins`’ `tasklists` raw HTML, keeps an `<input>` in `sanitized` mode only as a disabled checkbox, removes a raw `<link>`, and styles the box by structure as well as by class; its other sanitizer and parser changes, that a `<button>` is always `type="button"` and no element keeps `form`, that each footnote’s note and a host’s `body_html` are sanitized, that an `svg` fence drops any `<input>`, and that a document defining `[x]` as a link shows the link and no box, a marker ending its line is text, and any whitespace between the brackets is an open box, reach no untrusted page unchecked, because Metabrowser’s own allowlist runs after KPress on every untrusted path (`kpress_adapter.inert_render`, `markdown_projection._hardened`, `markdown_projection_worker._render`); runtime dependencies unchanged; lock delta is `kpress` alone, wheel SHA-256 `205d7f58…f9a28ab1` and sdist `8a00b909…cd5c110e` match `uv.lock` |
| `flowmark-rs==0.3.2` | `0.3.1` | Formatting output unchanged |
| `softschema==0.8.1` | `0.8.0` | Runtime contract validation; adds SoftSchema and upgrades `frontmatter-format` from 0.3.0 to 0.4.0 |
| `softschema==0.9.1` | `0.8.1` | Portable YAML guards and explicit validation execution. Release clears the ordinary cool-off. See [SoftSchema 0.9 review](#softschema-09-review). |
| `tryscript==0.3.0` | `0.1.7` | Removes the vulnerable fast-glob/micromatch/braces chain; adds tinyglobby discovery and the tsx loader |
| `tryscript==0.3.1` | `0.3.0` | Security patch only; upgrades zod from 3.25.76 to 4.6.6 for GHSA-mrhx-c7xc-m3w5 |
| `tryscript==0.4.0` | `0.3.1` | Replaces tinyglobby with tryscript’s own matcher, removing tinyglobby, fdir, and picomatch and with them GHSA-fc5q-39xc-vjpf; rejects extended globs, alternation groups, and brace ranges in test patterns, none of which this repository uses |
| `get-tbd` | n/a | Issue tracker, first-party; not a build or runtime input |

Tryscript 0.3.0 is a first-party exception to the release-age delay.
Its published registry tarball was selected explicitly during lock generation, then the
manifest was normalized to the exact `0.3.0` version.
The 14-day npm setting remained enabled for transitive resolution and remains enabled
for installs. The published artifact SHA-512 matches the committed lockfile:
`kvAtOGZZyTV8IqaSXVdbLB1OarRTlRqLqUefjVQ/xdqU9YgX1afivF4DZImrv4Uay4ehxoAysIqfMU1jtpOfYg==`.

The
[upstream release comparison](https://github.com/jlevy/tryscript/compare/v0.2.1...v0.3.0)
includes the discovery replacement and its unreadable-directory and negation fixes.
Compared with our prior 0.1.7 pin, the new dependency branches are tinyglobby 0.2.17
with fdir 6.5.0 and picomatch 4.0.7, and tsx 4.23.1 with esbuild 0.28.2 and optional
fsevents 2.3.3. All these third-party releases predate the 14-day cutoff; the newest was
picomatch 4.0.7 on 2026-08-24. The esbuild platform packages have the same 0.28.2
version and are optional platform selections.
No browser asset or Python runtime dependency changes.
Install scripts remain disabled; the full golden suite exercises the installed runner,
and the dependency audit took no exception for the advisory the removed chain carried.
picomatch 4.0.7, one of the branches this selection added, later drew
GHSA-fc5q-39xc-vjpf; tryscript 0.4.0, below, removed that branch.

Tryscript 0.3.1 is the same first-party exception, taken on 2026-10-26 because 0.3.0
reaches the vulnerable zod 3.25.76 and `npm audit` fails on GHSA-mrhx-c7xc-m3w5 (high,
memory exhaustion validating oversized constrained collections).
It was selected with `--min-release-age=0`, which npm applies to the whole command and
not to one package, so zod was resolved without the age gate too; the exact zod release
it pins was checked against the cool-off by hand instead, below.
`.npmrc` is unchanged, so the 14-day setting still governs every later resolution and
install. The published artifact SHA-512 matches the committed lockfile:
`terhA9EdYrHD9a2ZBMksJv/8lsDBye78KM+1SJnVdM7Fo+0Byk2yjpkbaLnDLLV87/GQqeDa/EDX7I8LitNdXw==`.

Two package versions change, and no package is added or removed: tryscript 0.3.0 to
0.3.1, and its pinned transitive zod 3.25.76 to 4.6.6. That is the whole lockfile delta,
four hunks, and it is reproducible from the base with one command:
`npm install --package-lock-only --save-exact tryscript@0.3.1 --min-release-age=0`. No
browser asset or Python runtime dependency changes.

An earlier revision of this entry also carried a `libc` field on four optional Biome
Linux platform packages, and described it as metadata recording a selection npm had
already made. Both halves of that were wrong, and the review of
[#269](https://github.com/jlevy/metabrowser/pull/269) caught it: the hunks came from an
upgrade-and-revert cycle that evaluated and then dropped the non-security upgrades, not
from this change, and a recorded `libc` is not inert.
`npm ci` checks it through Arborist’s platform test, so the variant whose libc does not
match is no longer installed: a Linux job that added 32 packages added 31. The hunks are
therefore removed rather than explained, which is also what keeps the delta reproducible
by the command above.
The lesson is the one this section already assumes: a lockfile hunk that no reviewed
change produced does not belong in the commit, whatever it appears to do.
zod 4.6.6 was published 2026-10-11, fifteen days before this selection, so the
transitive upgrade satisfies the ordinary cool-off on its own and needs no exception.
The [upstream release](https://github.com/jlevy/tryscript/releases/tag/v0.3.1) is a
security patch: the zod floor, explicit string keys in configuration records, nested
entry paths in union validation warnings, and development-only Vitest, Vite, and
source-map-js advisories that this repository does not install.
Golden parsing is unaffected — the full 278-check golden suite passes unchanged at
0.3.1, which is the behavior the 0.3.0 selection had to realign.

Tryscript 0.4.0 is the same first-party exception, taken on 2026-11-17 because 0.3.1
reaches picomatch 4.0.7, through tinyglobby 0.2.17 and fdir 6.5.0, and from that day
`npm audit` failed on
[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf) (high, a
regular-expression denial of service through single-branch repeated extglobs), which no
picomatch release fixes.
That was the advisory’s only path into the lock, and
[#523](https://github.com/jlevy/metabrowser/pull/523) tolerated it on that path alone
until a release removed it.
The [upstream release](https://github.com/jlevy/tryscript/releases/tag/v0.4.0) replaces
tinyglobby with tryscript’s own matcher, which builds no regular expression from a
pattern, so 0.4.0 depends on none of the three.
This selection removes that exception with its check, its tests, and its fixture, so the
audit again fails on any advisory at or above its level.
The wrapper keeps what #523 fixed apart from the exception: a report is a finding even
when an advisory’s title names an outage (see [Automated Checks](#automated-checks)).

It was selected with `--min-release-age=0`, as 0.3.1 was, and npm applies that to the
whole command; but the command moved no other package and added none, so no third-party
release entered the lock without the age gate.
`.npmrc` is unchanged.
The published artifact SHA-512 matches the committed lockfile:
`65hMMeYB0gDCHtbCFSOY1vIwVjlYrAHqYor4IoeaBwDqn8L7KE/RBD644qv+88WgFUtwmlg9paTit8yjf8Zk7A==`.
Its npm provenance attestation names the `v0.4.0` tag of jlevy/tryscript, commit
`4f33b3ccbc7aa7c470a6b1b25649eee5457957d7`, built by that repository’s release workflow.

One package version changes, three packages are removed, and none is added: tryscript
0.3.1 to 0.4.0, and tinyglobby 0.2.17, fdir 6.5.0, and picomatch 4.0.7 removed.
That is the whole lockfile delta, six hunks, and it is reproducible from the base with
one command:
`npm install --package-lock-only --save-exact tryscript@0.4.0 --min-release-age=0`.
tryscript’s own dependencies lose tinyglobby and are otherwise unchanged.
`npm ls picomatch` is empty.
No browser asset or Python runtime dependency changes.

0.4.0 is a minor release because it stops the run with an error on a test pattern that
uses an extended glob such as `+(a)`, an alternation group such as `(a|b)`, or a brace
range such as `{1..3}`, and because it reads parentheses in a pattern literally.
None of that reaches Metabrowser: its one test pattern is the Makefile’s
`tests/golden/*.tryscript.md`, which `make test` and `make golden-update` pass, and no
tryscript configuration file exists to add another.
The release’s discovery fixes concern negations, dot directories, and symbolic links,
and that pattern has no negation and names one directory, which holds no dot entry and
no link. The full golden suite passes unchanged at 0.4.0, and
`tests/test_tryscript_blocks.py` still finds the installed parser in agreement with
`devtools/tryscript_blocks.py`.

`get-tbd` carries no version review because it is not pinned to one, and the reason is
narrower than “we publish it.”
The exact selected release still receives the review this section requires: predecessor,
lock delta, dependencies, published artifacts, and the package’s actual reach.
For `get-tbd`, that reach remains narrow: nothing in the build, CI, test, or publishing
path runs it, so a bad release costs a developer’s session, not a release artifact.

The hook configs, session scripts, and agent skills are generated by `tbd setup` and
committed exactly as generated.
Editing them locally only means the next upgrade reverts the edit and someone has to
notice — which is what happened twice before this repository stopped patching them.

**Accepted cost of that choice:** the generated hooks call
`npx --yes get-tbd@<tbd_fallback_version>` without `--min-release-age=0`, and `.npmrc`
sets `min-release-age=14` with no per-package exclusion in npm.
So for fourteen days after every tbd release the fallback fails:

```
npm error code ETARGET
npm error notarget No matching version found for get-tbd@0.7.1 with a date before ...
```

That path is only reached when the local `tbd` CLI is missing or cannot read this
repository’s format, so a developer who installed tbd the standard way never sees it.
Anyone who does can install it — `npm install -g get-tbd@latest` — or run the one-off
with `--min-release-age=0`, which is the exemption this table grants, applied by hand
rather than baked into a generated file that the next upgrade would rewrite.

The exceptions are package-scoped in configuration and do not weaken the global gate.
Changing any of these versions requires a new review against the checks above.

### SoftSchema Review (September 15, 2026)

`softschema==0.8.1` provides the installed contract registry, deterministic JSON Schema
compilation, and structural plus Pydantic semantic validation used for the repository
cache’s records. It is reviewed against 0.8.0. The Python change makes cross-field
Pydantic errors JSON-serializable; its runtime dependencies are otherwise unchanged.
The locked wheel SHA-256 is
`7a68e52483c7a8ab63e541bb3d0329dd728096a2c256ef501e9658175540d6ad`; the source archive
SHA-256 is `e368eed680bf970b22790f4d90770dbdee290bedd6c0975ac51a6f1461b394e7`.

SoftSchema requires `frontmatter-format>=0.4.0`, so the existing runtime selection moves
from 0.3.0 to 0.4.0. That release adds deterministic alias-free YAML serialization and
in-memory frontmatter splitting without adding a runtime dependency.
Its locked wheel SHA-256 is
`71d6b416c6b05242d934b6228d2386311f2f9216d4d1d47549e6cadf7963fe76`; the source archive
SHA-256 is `dd7bc579b50e12a236c03427826a9af14fd2029e20dcae927e68f7440538e75a`. The lock
update must add SoftSchema, upgrade Frontmatter Format, and change nothing else.
The full verification gate reran the hosted-review codecs, schema compilation checks,
installed-wheel smoke tests, and dependency audits.
The hosted-review codecs were later removed from the v0.12 stack; SoftSchema now
validates the repository cache’s record contracts, and the same gate reruns their schema
compilation checks and installed-wheel smoke tests.

### SoftSchema 0.9 Review

[SoftSchema 0.9.1](https://pypi.org/project/softschema/0.9.1/) adds portable YAML
checks, validation execution reporting, and a guarded C parser.
Its MIT license and source repository match the prior pin.
The updated requirement excludes `ruamel.yaml==0.19.0`, which the current lock already
avoids. Metabrowser requires a completed validation at the existing configuration and
guided-review gates.

[Frontmatter Format 0.5.1](https://pypi.org/project/frontmatter-format/0.5.1/) fixes
line-separator round trips and applies the same C-parser guard.
Its MIT license, source repository, and only runtime dependency, `ruamel.yaml`, are
unchanged. Both releases were published on October 26, 2026. Their wheel and source
archive hashes match PyPI and `uv.lock`. The global cool-off admits both releases.

[`ruamel.yaml.clib==0.2.15`](https://pypi.org/project/ruamel.yaml.clib/0.2.15/) is the
optional native parser SoftSchema uses on CPython.
Anthon van der Neut publishes it under the MIT license from the
[ruamel-yaml-clib source repository](https://sourceforge.net/p/ruamel-yaml-clib/code/ci/default/tree/).
The November 16, 2025 release has no Python runtime dependencies.
Its wheels contain the `_ruamel_yaml` extension and distribution metadata.
The source archive builds that extension on platforms without a matching wheel.
The macOS arm64 and Linux x86-64 CPython 3.14 wheel hashes and the source archive hash
match PyPI. Non-CPython installs use the pure reader.
These three packages are the entire lockfile package delta.

## Admitted Git in CI

Production refuses repository acquisition below the Git security floor in
`tests/fixtures/repository-cache/git-version-gates.json`. Ubuntu’s packaged Git is below
it, and the Git on the CI runner image is whatever that image ships, which this
repository does not pin.
The `admitted-git` CI job therefore builds Git from source, so acquisition and the
full-clone acceptance tests run on releases production admits: the lowest admitted
release and the newest patched one.
It builds a third, the oldest it tests that reads file ages on a Git revision
(`git last-modified`, `FILE_AGES_GIT_MINIMUM` in `src/metabrowser/git/file_ages.py`), so
the present path of that feature runs in CI whichever Git the runner image ships and the
other two builds exercise the absent one.

| Release | Role | SHA-256 of `git-<release>.tar.xz` |
| --- | --- | --- |
| 2.43.7 | Lowest admitted release | `657e2374455d9e62f6cdb3e7c55d867b6db5404d744e97e112cc5b0db687a19f` |
| 2.50.1 | Newest patched release | `7e3e6c36decbd8f1eedd14d42db6674be03671c2204864befa2a41756c5c8fc4` |
| 2.56.1 | Reads file ages (`git last-modified`) | `f0b0bf89264b9bd2e1c640363e7529643989da76281600473c50745cd34a607f` |

- **Source.** The archives come from
  `https://mirrors.edge.kernel.org/pub/software/scm/git/`. The checksums were copied
  from that directory’s `sha256sums.asc`, fetched on September 22, 2026. That file is
  signed with the kernel.org checksum autosigner key
  `B8868C80BA62A1FFFAF5FDA9632D3A06589DA6B1`; the signature was not verified when the
  checksums were copied.
  The 2.50.1 values also match those recorded independently in the tracking issue.
  The 2.56.1 value was first copied from Homebrew’s `git` formula, whose `url` is that
  directory’s `git-2.56.1.tar.xz`, and it matches the `git-2.56.1.tar.xz` line of that
  directory’s `sha256sums.asc`, checked on November 20, 2026; the signature on that file
  was not verified. The build fails closed on a wrong value.
- **Cool-off.** The 2.43.7 and 2.50.1 archives were published on July 8, 2025, in the
  security batch the version floor is based on, so they are well past the 14-day
  cool-off. The 2.56.1 tag is dated October 26, 2026, 25 days before the pin.
- **Build.** `devtools/build_admitted_git.sh` holds the pins and builds only a pinned
  release. It downloads over HTTPS only and checks the SHA-256 before unpacking.
  It builds without Tcl/Tk, gettext, Perl, Python, Expat, or OpenSSL. Its only other
  inputs are `libcurl4-openssl-dev` and `zlib1g-dev` from the runner’s own Ubuntu
  archive.
- **Reach.** The build is cached with `actions/cache` v6.1.0, keyed by runner image,
  release, and a hash of the build script, so a changed pin or recipe rebuilds.
  That release was published June 26, 2026. Only the `admitted-git` job puts the build
  on `PATH`. Nothing in the wheel, the other jobs, or the publish workflow uses it.

`devtools/check_supply_chain.py` requires this table, the script’s pins, and the job’s
matrix to agree, and requires the matrix to include both floors from the version-gates
fixture. Moving a floor therefore means pinning and reviewing the new release here.

## CI Workflows

`ci.yml` and `nightly.yml` give every job `contents: read`, and two jobs one permission
more, reviewed on November 17, 2026:

| Workflow | Job | Permission | What it reads |
| --- | --- | --- | --- |
| `ci.yml` | `plan` | `actions: read` | One page of `ci.yml`’s push runs on `main`, and the earlier attempt of a rerun, to learn whether `main` is red (`devtools/ci_plan.sh`) |
| `nightly.yml` | `time-limits` | `actions: read` | `ci.yml`’s push runs on `main` and their jobs, for `make ci-report` |

- **Reach.** `actions: read` reads this repository’s workflow runs, jobs, logs, and
  artifacts, and writes nothing.
  The repository is public, so it reads nothing an anonymous reader cannot; it is
  declared so that the token’s scope is stated, not inherited.
  No job may write issues, pull requests, or contents.
- **Triggers.** `ci.yml` runs on a push to `main` and on `pull_request`, never on
  `pull_request_target` or `workflow_run`. A pull request’s run therefore gets a
  read-only token, and its workflow and the `devtools/ci_plan.sh` and
  `devtools/ci_verdict.sh` it runs come from the pull request’s own merge commit, so a
  change to the gate is reviewed as a change.
  `nightly.yml` runs on a schedule and by hand.
- **Untrusted input.** A branch name or a pull request’s title or body reaches a step
  only through `env:`, quoted in the shell; no `run:` line or step input interpolates
  the event. The `plan` job refuses a run id or head from the API that is not one, and
  counts that answer as red, like a failed read.
- **Nightly report.** The `time-limits` job installs its locked environment in a step
  without the token, so the step that holds the token runs only `ci-report`.
- **Actions.** No new action: the jobs use the pinned checkout, uv, Node, and cache
  actions already reviewed, and the runner image’s own `gh` and `jq`. Every checkout
  sets `persist-credentials: false`.
- **uv.** Before each setup-uv step, `devtools/install_uv.sh` fetches the same pinned uv
  release archive from GitHub Releases over HTTPS, refuses it unless its SHA-256 is the
  one that step pins, and puts it in the runner’s tool cache, so setup-uv neither
  downloads uv nor fetches its version manifest.
  The manifest fetch has a fixed 5 s limit and no retry, and one slow answer failed a
  job; the script retries instead.
- **Node.** Before each setup-node step, `devtools/install_node.sh` fetches the archive
  setup-node would download from an `actions/node-versions` release, over HTTPS, refuses
  it unless its SHA-256 is the one the script pins for the runner’s platform, and
  unpacks it into the runner’s tool cache, so setup-node neither downloads Node nor
  copies it there. setup-node checks no checksum, so the pins are new.
  Reviewed on November 25, 2026: for Node 24.18.0 the script pins release
  `24.18.0-28070977815`, published June 24, 2026, and each archive’s SHA-256 is the
  digest GitHub records for that release asset.
  setup-node v6.4.0 has no manifest of its own: it reads `versions-manifest.json` from
  `actions/node-versions` at `main` when it runs, and on that date the manifest named
  this release for both platforms’ 24.18.0 archives.
  The download had no limit on a slow transfer and the copy went file by file, and each
  stalled for over a minute (mb-z4i7); the script ends a stalled transfer and retries,
  and unpacks in place.

`devtools/check_ci.py`, in `make lint-check`, fails:

- in any workflow, a job whose permissions are not declared, at its own level or the
  workflow’s, or that grants any `write` but `publish.yml`’s `id-token`;
- in `ci.yml` and `nightly.yml`, a job given a permission this table does not name;
- a `pull_request_target` or `workflow_run` trigger, and a checkout that keeps its
  credentials;
- an expression in a `run:` line, or in a step’s `with:` other than a commit or a
  release tag, that reads the event, the head branch, or the whole `github` context, in
  any spelling or case: `github.event.`, `github['event']`, `toJSON(github)`,
  `GitHub.Head_Ref`, or inside `format()`, with the expression ended where the runner
  ends it, so a `}}` in a quoted string hides nothing;
- an expression in a `run:` line that reads `env`, which the shell reads as `"$NAME"`
  instead;
- a setup-uv step that does not come just after `devtools/install_uv.sh` with its own
  version and checksum;
- a setup-node step that does not come just after `devtools/install_node.sh` with its
  own version.

## Apple Developer ID Intermediate (November 17, 2026)

`apps/macos/packaging/DeveloperIDG2CA.cer` is Apple’s “Developer ID - G2” intermediate
certificate, committed so that the release Mac, and later a CI release job, installs it
from the repository instead of downloading it.
codesign builds a Developer ID identity’s chain from the keychains on the search list,
and macOS’s own roots hold only the G1 intermediate, so without this file a G2 identity
is not valid.

| File | SHA-256 |
| --- | --- |
| `DeveloperIDG2CA.cer` | `f16cd3c54c7f83cea4bf1a3e6a0819c8aaa8e4a1528fd144715f350643d2df3a` |

- **Source.** Downloaded on November 17, 2026, from
  `https://www.apple.com/certificateauthority/DeveloperIDG2CA.cer`, the link
  [Apple PKI](https://www.apple.com/certificateauthority/) gives for it, and committed
  unchanged (DER, 1,090 bytes).
  Its subject is `CN=Developer ID Certification Authority, OU=G2, O=Apple Inc., C=US`,
  its issuer is Apple Root CA, and it is valid from September 22, 2021, to September 17,
  2031\.
- **Chain.** `openssl verify` accepts it against Apple Root CA, downloaded from Apple
  PKI at `https://www.apple.com/appleca/AppleIncRootCertificate.cer`, whose SHA-256
  fingerprint is `b0b1730ecbc7ff4505142c49f1295e6eda6bcaed7e2c68c5be91b5a11001f024`.
  That root is committed as `apps/macos/scripts/fixtures/AppleIncRootCertificate.cer`,
  so `apps/macos/scripts/test-release-logic.sh` repeats the check on every test run, and
  the signing doctor (`apps/macos/scripts/check-signing.sh`) repeats it on the release
  Mac against the Apple Root CA in macOS’s own roots.
- **Pin.** `g2_intermediate_sha256` in `apps/macos/scripts/signing-lib.sh` holds the
  SHA-256 above. The doctor refuses a file that does not match it, and an installed
  certificate with this subject and other contents.
  `apple_root_ca_sha256` in `apps/macos/scripts/test-release-logic.sh` holds the root’s,
  and the test checks the fixture against it before the chain.
  `tests/test_macos_release_scripts.py` holds both values here to their pins, and each
  pin to its file.
- **Reach.** It is a public certificate and grants nothing by itself: installing it lets
  macOS build the chain of an identity Apple already issued.
  Replacing it is a new review here, with the pin changed in the same commit.

## Verification

### Development HTTP Client Review (September 8, 2026)

The locked development-only `httpx2` and `httpcore2` packages move from 2.5.0 to 2.12.0
to resolve the five advisories reported by `uv audit`. The
[HTTPX2 changelog](https://github.com/pydantic/httpx2/blob/main/src/httpx2/CHANGELOG.md)
and
[transport changelog](https://github.com/pydantic/httpx2/blob/main/src/httpcore2/CHANGELOG.md)
describe the fixes.
Both releases were published on August 18, so they satisfy the 14-day
cool-off without an exception.
Registry artifact hashes match `uv.lock`; the Python requirement remains compatible with
this project’s supported range.

The only new transitive record is `httpx2-jsfetch==1.0`, published August 7 and required
by upstream solely on Emscripten.
It is not installed on the project’s native test platforms.
The published application gains no runtime dependency.
No unrelated lock versions change.
The normal full verification gate exercises the upgraded test client and audits the
complete lock.

### Locked AnyIO Review (September 18, 2026)

The locked transitive `anyio` package moves from 4.14.1 to 4.14.2 to resolve the three
advisories reported by `uv audit`: GHSA-5p39-cfhj-2xmp, GHSA-82r6-8w77-94w6, and
GHSA-3w57-8xmc-8v26. The
[AnyIO version history](https://anyio.readthedocs.io/en/stable/versionhistory.html)
describes the fixes.
The release was published on July 12, so it satisfies the 14-day cool-off without an
exception. Registry artifact hashes match `uv.lock`; the Python requirement remains
`>=3.10`, compatible with this project’s supported range.

Starlette and Uvicorn already depend on AnyIO; no new transitive records appear.
No unrelated lock versions change.
The normal full verification gate audits the complete lock.

### Direct Pygments Requirement (November 11, 2026)

`diff/markdown_projection.py` reads the lexer aliases Pygments ships to decide which
fence info strings name a language, so `pygments>=2.20.0` is now declared directly.
KPress already requires Pygments, and so does pytest, so the lock gains no package and
no version changes: the delta is the two lines that name Pygments among this project’s
requirements. The locked release, 2.20.0, was published on March 29, 2026, so it
satisfies the 14-day cool-off without an exception.
Its source is [pygments/pygments](https://github.com/pygments/pygments), its license is
BSD-2-Clause, and its Python requirement, `>=3.9`, covers this project’s supported
range. Its registry artifact hashes in `uv.lock` are unchanged.

### Mermaid (November 18, 2026)

`mermaid` 12.3.0 is a new development dependency, vendored by
`devtools/vendor_assets.py` into `src/metabrowser/static/vendor/mermaid/` so Markdown
documents draw their Mermaid diagrams as GitHub does.
12.3.0 is the release GitHub’s own renderer embeds, and nothing in this repository draws
diagrams without it.
Its source is [mermaid-js/mermaid](https://github.com/mermaid-js/mermaid), published by
that project’s maintainers, and its license is MIT. It was published on November 3,
2026, so it satisfies the 14-day cool-off without an exception, and `min-release-age` in
`.npmrc` held every transitive release to the same age at install.

The lock delta is 116 added packages and the root entry’s new pin: no existing package
changes version or record, and none of the added ones has an install script.
Their licenses are MIT (67), ISC (33), Apache-2.0 (6), BSD-3-Clause (6), Unlicense (1),
DOMPurify’s MPL-2.0 or Apache-2.0, elkjs’s EPL-2.0 or GPL-3.0-or-later, and khroma’s MIT
license file with no declared field; [NOTICE.md](NOTICE.md) records how they apply.
The vendored tree is only the ESM entry and its chunks; source maps are left out, and
`TOTAL_CAP_BYTES` in `devtools/vendor_assets.py` records the measured size.
The browser imports the entry only for a document with a diagram, and Mermaid runs with
`securityLevel: "strict"`, which sanitizes labels and disables `click` callbacks.

### Node Type Declarations (November 11, 2026)

`@types/node` 24.19.2 is a new development dependency.
`make lint-check` now type-checks the WebKit gate’s Node modules strictly
(`apps/macos/webkit-gate/tsconfig.json`), and Node’s own modules have no declarations
without it. Its source is
[DefinitelyTyped](https://github.com/DefinitelyTyped/DefinitelyTyped), its license is
MIT, and it has no install scripts: it ships declaration files, a README, and a license.
The release was published on October 9, 2026, so it satisfies the 14-day cool-off
without an exception, and its 24.x line matches the Node 24 release CI pins.
Its one dependency, `undici-types` 7.24.6 from
[nodejs/undici](https://github.com/nodejs/undici) (MIT, declarations only, published
March 25, 2026), is the only other new lock record.
Neither is loaded at run time; only TypeScript reads them.

### pytest-xdist Review (November 17, 2026)

`pytest-xdist` is a new development dependency, and `execnet`, its one requirement that
the lock did not hold, comes with it.
`make test-parallel` and `make test-admitted-git` run their tests under it, one worker
per logical processor and each test file on one worker (`--dist loadfile`), so a CI test
leg uses its runner’s four processors where pytest alone used one.
pytest has no way to run tests side by side without a plugin, and the owner approved
this one on 2026-11-16.

| Package | Release | Published | Source | License | Wheel SHA-256 | sdist SHA-256 |
| --- | --- | --- | --- | --- | --- | --- |
| `pytest-xdist` | 3.8.0 | 2025-07-01 | [pytest-dev/pytest-xdist](https://github.com/pytest-dev/pytest-xdist) | MIT | `202ca578…d10f0b88` | `7e578125…d8d3a9f1` |
| `execnet` | 2.1.2 | 2025-11-12 | [pytest-dev/execnet](https://github.com/pytest-dev/execnet) | MIT | `67fba928…79e296ec` | `63d83bfd…3e0befcd` |

- **Cool-off.** Each is the newest release of its package, and each was published more
  than a year before this selection, so neither needs an exception.
- **Artifacts.** The four digests above were read from PyPI and match `uv.lock`, and the
  artifacts downloaded for this review hash to them.
  Both wheels are pure Python, `py3-none-any`, and hold no `.pth` file, console script,
  or compiled module, so installing them runs no code.
  The sdists build with setuptools and hatchling; uv installs the wheels.
  PyPI holds a Trusted Publishing attestation for each of the four files, naming the
  `deploy.yml` workflow and `deploy` environment of `pytest-dev/pytest-xdist` and
  `pytest-dev/execnet`.
- **Import.** The xdist wheel registers two `pytest11` entry points, `xdist.plugin` and
  `xdist.looponfail`, so every pytest run in this environment imports them and gains
  their options, the serial and Chrome tiers’ runs too.
  `xdist.looponfail` imports `execnet` at module level, so every run imports that as
  well. The imports open no socket and start no process; without `-n` or `--dist` nothing
  starts.
- **Runtime.** With `-n`, xdist starts each worker through execnet’s `popen` gateway: a
  new `sys.executable` that reads execnet’s bootstrap from a pipe and sends its reports
  back over the same pipes.
  execnet’s `ssh`, `socket`, and `rsync` gateways open network connections, and nothing
  here asks for them. execnet also ships scripts under `execnet/script/`, and
  `socketserver.py` among them listens on a TCP port and runs what a client sends.
  Three of them act only when run as a program; `shell.py` and `quitserver.py` connect
  to the address their command line names when imported.
  Nothing runs or imports them: the wheel gives them no console script, and the one
  import, of `socketserver`, is in the `socket` gateway’s start.
  `-n auto` counts physical cores through psutil, which this project already installs,
  so `PYTEST_WORKERS` in the `Makefile` asks for `logical` instead and says why.
- **Lock delta.** The two packages, and `pytest-xdist` among the `dev` group’s
  requirements, and nothing else; pytest, xdist’s other requirement, is already locked.
- **Reach.** Development only: neither is a runtime requirement, in the wheel, or used
  by the publish workflow.

### psutil Is Development Only (November 24, 2026)

`psutil` moves from the runtime requirements to the `dev` group.
No code in the package imports it: `devtools/git_history_benchmark.py` samples memory
with it, and pytest-xdist’s `-n auto` reads physical cores through it, both in
development.
`devtools/check_plugin_deps.py` now fails a runtime requirement that neither
core nor a built-in plugin imports, which is how this one was found.
- **Lock delta.** `psutil` leaves the package’s `dependencies` and `requires-dist` and
  joins the `dev` group’s; the locked release and its artifact hashes are unchanged.
- **Reach.** The wheel, and the macOS app that bundles its requirements, no longer
  install a compiled extension that nothing at run time uses.

### pypdfium2 Review (November 24, 2026)

`pypdfium2` is a new runtime dependency of the `pdf` plugin alone (its manifest’s
`python_requires`, which `devtools/check_plugin_deps.py` keeps true).
It is Python’s binding to PDFium, the PDF engine of Chrome, and draws the first page of
a PDF for the plugin’s preview card.
It is the one maintained binding that ships PDFium prebuilt for every platform this
package supports and needs no imaging library; the plugin encodes the PNG with the
standard library (`render_child.py`). PDFium parses bytes a content author wrote, so it
never runs in the server: each render is a child process with resource limits, and for
an untrusted source an OS sandbox (threat model T7 in
`docs/project/architecture/arch-threat-model.md`).

| Package | Release | Published | Source | License | Wheel SHA-256 | sdist SHA-256 |
| --- | --- | --- | --- | --- | --- | --- |
| `pypdfium2` | 5.15.2 | 2026-11-09 | [pypdfium2-team/pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | BSD-3-Clause, Apache-2.0, and PDFium’s dependencies’ licenses | macOS arm64 `e71fe832…c2a44c35`, Linux x86_64 `dc31aea5…85161e37` | `0185193b…d2ce2aef` |

- **Cool-off.** 5.15.2 is the newest release, published fifteen days before this review,
  so it passes the 14-day `exclude-newer` window without an exception.
  PyPI lists no known vulnerability for it.
- **Artifacts.** `uv.lock` holds the sdist and 22 wheels, and their 23 digests match the
  ones PyPI lists for the release.
  PyPI holds a Trusted Publishing attestation for the files, naming the project’s
  `main.yaml` release workflow.
  The wheels are `py3-none-<platform>`: the Python binding, and a bundled `libpdfium`
  built from PDFium’s sources by the project’s toolchain (`pypdfium2 --version` reports
  `pdfium 159.0.8149.0@sourcebuild-toolchained`), built without V8 or XFA, so it runs no
  JavaScript in a PDF and parses no XFA form.
  The macOS arm64 wheel installed here holds no `.pth` file; its one console script,
  `pypdfium2`, is a command line nothing here runs.
- **Import.** Only the render child imports it (`render_child.py`, run by path in a
  child process); the server process loads only its version file to name the renderer in
  each preview’s cache key (`preview.renderer_version`).
- **Lock delta.** The one package, and `pypdfium2>=5.15.2` among the package’s
  `dependencies`; it requires nothing else.
- **Reach.** The wheel, and so the macOS app that bundles its requirements, install it
  and its native library (7.6 MB installed on macOS arm64, from a 3.7 MB wheel).
  A disabled `pdf` plugin never starts the child.

### Automated Checks

`devtools/check_supply_chain.py` checks only safeguards that span configuration files:
npm safety settings, exact direct npm specifications, npm registry and integrity data,
the uv cool-off, matching nvm and fnm versions, full-SHA action references, and trusted
publishing controls.

The configuration files own dependency versions, build behavior, lint and type ratchets,
workflows, and documentation.
`make verify` installs both locks, runs the configured linters and type checkers,
executes the tests and audits, builds the package, inspects its contents, and exercises
the installed wheel and plugin surface.

CI and publishing also run `npm audit --include=dev --audit-level=moderate` after
installing the exact lock, through `devtools/npm_audit.sh`. That wrapper exists because
`npm audit` exits non-zero for two unrelated events: it found an advisory, or it could
not reach the advisory endpoint.
Only the first is a reason to stop.
npm writes its report to stdout and its own errors to stderr, and the wrapper keeps them
apart. A report is a finding and fails, whatever its advisories’ titles say, and even if
npm also warned on stderr about a failed request.
Only when there is no report does the wrapper search stderr for an unreachable endpoint.
It retries, then reports the outage as **not performed** -- loudly, and without failing
the build, because a registry outage is not a finding and the lockfile is pinned, so the
dependency set has not moved since the last run that did reach it.
Any other npm failure, such as a missing lockfile, fails, and so does an
`NPM_AUDIT_ATTEMPTS` that is not a positive integer.
Every npm package in this lock is a dev dependency, so `--include=dev` keeps an ambient
`NODE_ENV=production` or `NPM_CONFIG_OMIT=dev` from reducing the audit to nothing.
`tests/test_npm_audit.py` runs the wrapper against a stand-in `npm` for each of these
cases. A run that reports “not performed” has not cleared the dependencies; re-run the
gate once the registry answers before relying on it.

Treat an unexpected lockfile source, install script, binary artifact, or publish-time
change as a blocker until it is explained and reviewed.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
