# The macOS App’s Contract with metab

**Status:** Enforced.
`devtools/check_app_contract.py` reads the declaration in `make lint` and
`make lint-check`, `tests/test_app_contract_golden.py` compares the golden,
`AppContractTests` in the app’s Swift tests reads it back, and
`tests/test_check_app_contract.py` checks the checker.
The release rule that [Versioning](#versioning) enforces is written in
[Choosing a Version](../../publishing.md#choosing-a-version), which marks the points the
owner has not yet decided.

The [macOS app](arch-macos-app.md) runs the `metab` a user installed, as a subprocess,
and talks to the server it starts.
The two update apart: uv upgrades `metab`, and the app is replaced by hand.
So a `metab` release can meet an app built before it, and an app can meet a `metab`
older than it expects.
Whatever the app reads of `metab` is therefore a contract, and this document is where
that contract is described: what it holds, the one file that declares it, the golden
that records it, and the checks that keep both sides to it.

## The Declaration

`apps/macos/metab-contract.toml` lists everything the app depends on in `metab`. It is
the only list: other documents name an example and link here, and
`python -m devtools.check_app_contract report` prints the inventory with its counts.

| Table | Holds | Held by |
| --- | --- | --- |
| `[[command]]` | A `metab` command the app runs, as an argument list with a placeholder for each value that varies, and what the app reads of its answer: the keys of a JSON object, the lines of a stream, or only the exit status. `shown` and `opaque` name the keys whose text the app only shows, or keeps unread | A block of the golden; `AppContractTests` |
| `[[route]]` | A route the app asks a ready server over HTTP, and the keys it reads | A block of the golden, asked with `--api`; `AppContractTests` |
| `[[line]]` | A line of output the app reads as text, as a pattern for the part it parses | The golden, another golden it names, or the test in `pinned_by` |
| `[[env]]` | A variable of `metab`’s that the app sets for a child | A block that sets it, in the golden or in another golden it names |
| `[[behavior]]` | What the app relies on that is neither a field nor a line: a server stopping when its stdin closes, the name of the executable, or a selector the app’s own script looks for in a page | What `pinned_by` names, and the copies golden for its `values` |
| `[[copy]]` | A value of `metab`’s that the app holds a copy of, such as the port its walk starts from | The test in `pinned_by`: a Python test that reads the Swift source, or a test of the app’s that reads the golden. The copies golden records each of its `values` |
| `[[app_side]]` | What `metab --present` reads of the app before it hands it a target | The test in `pinned_by`, and the copies golden |
| `[files.*]` | Every Swift file that starts a process, decodes JSON, sends a request, or scripts a page, with what it runs or reads | The source search in `check_app_contract.py` |

A `pinned_by` takes two forms.
A test function is `path::name`, in a Python module or one of the app’s Swift suites.
A browserless session under `tests/dom` or a golden is its path alone, with the text in
`holds` that the file must contain.
The second form is for what the app’s own script relies on in a page, such as a
selector: the page’s side of that is pinned by the session that renders it, which no
Python or Swift test names.

A command with `app_runs = false` is one the app never runs.
The golden needs it to show something the app depends on, and `because` says what: the
answer a build gives an option it does not know, the address `metab` announces for a
file, and the command the status view tells a person to try in Terminal.

The file sits beside the app because it is the app’s statement of what it consumes.
A Markdown table in this document, as the [parity registry](arch-parity-registry.md)
has, would have put argument lists and key paths in table cells; a Python module could
not have been read as a declaration by someone working on the app.
The Swift tests do not read the file.
They read the golden, which the declaration generates, so the two languages meet at one
committed transcript and neither needs a parser for the other’s format.

## The Golden

`tests/golden/app-contract.txt` is one transcript of the whole surface.
`tests/test_app_contract_golden.py` writes it: for each declared command and route it
fills the argument list, runs it through the console script’s entry point, and records
the exit status and what the declaration says the app reads.

- **Only what the app reads is recorded.** A JSON answer is cut to its declared keys,
  and a line to the part its pattern matches.
  A field `metab` adds for another reader leaves the transcript as it was, so a change
  to the transcript means that something the app reads changed.
  The whole answers stay pinned where they always were, in the transcript of each mode.
- **A declared key that an answer lacks fails the driver.** A renamed key cannot pass as
  an omission.
- **Text the app only shows is recorded as present.** A refusal’s message, the reason a
  list is empty, and the rest of a clone’s line are shown to a person as `metab` wrote
  them, and a cursor is handed back unread.
  The transcript holds `<text>` or `<opaque>` for each, after the driver has checked
  that a string is there, so rewording a message changes nothing here.
  A value stays exact where the app branches on it or compares it: a `kind`, a state, a
  URL it matches.
- **A command’s answer keeps its framing.** The app finds a JSON answer by the lines of
  one pipe that carries both streams: a line that is exactly `{`, and one that is
  exactly `}`. So the driver writes the declared keys in the framing `metab` printed the
  whole answer in, with whatever it printed before and after, and records the lines of
  stderr that such a reader would take.
  An answer printed on one line changes the transcript, and then fails the app’s reader
  in `AppContractTests`. A route’s answer is re-serialized, because the app decodes a
  response whole.
- **The command line is the app’s.** The Swift tests require the app’s own builders to
  write each one.
- **Each block names its scenario** in a `contract` section, which is how the Swift
  tests find it.

`tests/golden/app-contract-copies.txt` is a second, small golden: a line for each
definition of `metab`’s that an entry names in `values`, as `metab` has it.
The pin tests already make the app’s copy follow a changed value in the same commit.
The line makes that change visible to the release rule, since an app already installed
keeps the old value.

The driver’s docstring says what differs from the app’s own runs and why: no server
listens, a route is asked with `--api`, and the repository is a `file://` origin.
Two lines of a clone’s report cannot be shown by a transcript, because `metab` writes
them only after a wait, and the `Error:` line of a failed start is shown by
`cli-github-not-found.txt`, which needs a stand-in for GitHub.
`tests/test_macos_app_pins.py` holds the app’s samples of all three to what `metab`
writes, and each such `[[line]]` names its test.

## The Checks

| Check | Runs in | Fails when |
| --- | --- | --- |
| `tests/test_app_contract_golden.py` | Every Python job | `metab` answers a declared command or route differently in anything the app reads, the lines of a JSON answer included; an answer lacks a declared key; a value the app copies is defined differently; `metab --version` prints a version `MetabVersion` cannot read; the console script or the distribution is renamed |
| `AppContractTests` | The macOS workflow, on a change under `apps/macos` or to the golden | A builder in the app writes a command line the golden does not have; a reader in the app reads a recorded answer as anything but its scenario; the golden gains or loses a scenario the suite does not follow |
| `check_app_contract.py`, the sources | `make lint-check`, in every job | A Swift source names a flag, a route, or a variable of `metab`’s or the interpreter’s that the declaration lacks; a file starts a process, decodes JSON, sends a request, or scripts a page and is not listed; a listed file reads a key by subscript or coding key that its entry lacks; the declaration names something the sources no longer do; the declared probe is not `MetabRequirement.requiredFlags` and `--version` |
| `check_app_contract.py`, the goldens | The same | A declared command or route has no block; a block’s command line is not the declared argument list; a block holds a key or a line the declaration does not, or the words of text the app only shows; a declared value or line is shown nowhere; a copied value has no line in the copies golden; a `pinned_by` names no test, or a file that lacks its `holds`; the macOS workflow’s path filter does not name the golden |
| `check_app_contract.py`, the changelog | The same | A branch changes the declared surface or a golden and no changelog fragment says so; a fragment calls a change to the declared surface a fix; a patch release’s section holds a change to the contract |

A problem that asks for a line in the declaration prints the line.

The Swift sources are read as text, by `devtools/swift_text.py`, which tells a string
literal from a comment.
That is the honest way to do it in a Python job, which has no Swift compiler, and it is
why the app’s builders and readers are held by the app’s own tests and not by a search.
What no search here finds, so review declares it:

- **A new reader of a line of output,** which is ordinary string handling.
- **A key read through an Optional property.** A subscript and a coding key’s raw value
  are searched; a bare property of a `Decodable` type is not, and a missing Optional
  reads as nil, so the app’s tests pass without it.
- **A command or a request the search’s words do not spell:** a `LaunchSpec` built as
  `.init(…)`, `webView.load(.init(url:))`, or `Data(contentsOf:)` on a server’s URL.
- **A short flag,** and a flag or a route assembled from parts.
- **A route not spelled `api/…`,** such as a page’s address.
- **What the app relies on in a page,** except through a script of its own.
  Every file that scripts a page is listed under `[files.script]`, and what its script
  looks for in the page is a `[[behavior]]`.

## Changing the Contract

1. Change `metab` and the app in one commit, as
   [AGENTS.md](../../../AGENTS.md#compatibility-and-legacy-code) asks.
2. Edit `apps/macos/metab-contract.toml`: the command, the keys read, the line.
3. Add or change the scenario in `tests/test_app_contract_golden.py`, run
   `make golden-update`, and read the diff of the two goldens.
4. Read the new scenario in `AppContractTests`, through the app’s own builder and
   reader.
5. Name the change in a changelog fragment, as [Versioning](#versioning) says, and raise
   `MetabRequirement.minimumRelease` if the app now needs the newer `metab`
   ([the version floor](arch-macos-app.md#the-version-floor)).

## Versioning

[Choosing a Version](../../publishing.md#choosing-a-version) holds the rule: a change to
what the app reads from `metab` ships in a minor or major release, and a bug fix that
keeps what the app reads may ship in a patch.
Two checks hold a release to it, and a tool asks any `metab`.

- **A change to the contract is named.** A branch whose declared surface or goldens
  differ from its merge base with `main` adds a changelog fragment with an entry that
  starts `- **App contract:**`. The declared surface is what the app depends on:
  commands, routes, keys, values, lines, variables, and each behavior, copied value, and
  thing `metab` reads of the app, and not a note or the test that pins an entry.
  A copied value that changes, such as the number of ports a walk tries, changes the
  copies golden, so it is named too and cannot ship as a patch.
  When only a golden differs, `metab` answers the same surface differently; if the old
  answer was a bug, the entry may start `- **App contract fix:**`, which is the fix that
  keeps what the app reads.
  A reworded message is neither, and changes no golden.
  The author knows which it is, and the release reads it later.
- **A patch release holds no change.** A section of `CHANGELOG.md` headed `X.Y.Z` with
  `Z` above zero may hold `App contract fix` entries and no `App contract` entry.
  The pull request that prepares a release adds that heading, so choosing a patch
  version for a release that changes the contract fails its `make lint-check`.
- **Any `metab` can be asked.**
  `python -m devtools.check_app_contract accepts /path/to/metab` runs each command the
  app runs with `--version` after it, which a `metab` answers before it reads any other
  option. A build that lacks a flag exits 2 naming it, which is the app’s own setup probe
  extended to every declared command.
  It starts nothing and writes nothing, and it asks no route, which needs a server.

A field or flag the app begins to read is new in the declaration, so it is a change and
ships in a minor release.
A field the app does not read is no part of the contract, and `metab` may add one in any
release without touching the golden.

## What the Contract Leaves Out

- **The page.** What a window shows is the web shell’s, which ships with its server, and
  the [parity registry](arch-parity-registry.md) holds that surface.
  The exception is what a script of the app’s own looks for in a page, which is declared
  here as a `[[behavior]]`.
- **Other tools.** The app runs `uv tool dir --bin` and a login shell, and shows `uv`
  and `gh` commands for a person to run.
  Their flags are listed under `[other]` so that the source search passes over them.
- **Timing.** How long a start may take is the app’s policy, built from copies of
  `metab`’s bounds, which are `[[copy]]` entries.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
