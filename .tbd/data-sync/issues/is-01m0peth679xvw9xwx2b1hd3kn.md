---
type: is
id: is-01m0peth679xvw9xwx2b1hd3kn
title: "A dev build should say it is one: dirty and ahead-of-tag markers in --version"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-23T04:42:22.263Z
updated_at: 2026-08-23T04:42:22.263Z
---
A build running from a source checkout reports a plain release version, with nothing saying it is not that release. `metab --version` said `0.6.0` while the code was 27 commits past the v0.6.0 tag, because `importlib.metadata.version()` returns what was recorded when the package was installed, and an editable install does not re-record it as commits land.

This is not a flaw in the pattern -- `python-cli-patterns` prescribes exactly this: derive from git tags, look up with `importlib.metadata`. The gap is that the lookup is a snapshot and the checkout keeps moving.

COST, twice in one session. Building a release candidate produced `0.5.2.dev132` when a `0.6.0` artifact was wanted, and the mismatch only surfaced because the publish workflow's own version gate was run by hand first. Then, setting up a side-by-side performance comparison, the candidate build reported `0.6.0` -- identical to the baseline it was being compared against. Attributing a timing number to the wrong build is the kind of error that survives a whole investigation, and nothing on screen would have contradicted it.

REQUESTED: a build that is not exactly a released version says so in `--version`.

- From a git checkout: commits since the tag and the short sha, and a dirty marker when the working tree has uncommitted changes. The dirty marker matters most -- it is the state that no version string can otherwise describe, and the state a developer is in nearly all the time.
- Installed from PyPI: unchanged. There is no repository to consult and the recorded version is the truth.
- The reported string stays parseable, and `metabrowser.__version__` keeps meaning the package version; a marker belongs in what `--version` prints, not in the field the publish workflow's tag check compares.

Points to settle:
- Where the git state is read. It has to be cheap and must never fail a normal run: no repository, no git binary, or a shallow clone all have to fall through to the recorded version silently.
- Whether the marker also belongs in the server's own startup line and the `--doctor` output, which are the other two places someone reads a version while deciding what they are looking at.
