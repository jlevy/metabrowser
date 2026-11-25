# Architecture: Recent Targets

**Status:** Built (`mb-40k4`): the store (`src/metabrowser/recent_targets.py`), its four
`metab` modes (`cli/recent_cli.py`), the record a serve makes, and the macOS app’s File
\> Open Recent, which lists what `metab --recent --json` answers.
Built (`mb-1q02`): only a serve someone opened to read records, the app’s open or a
person’s at a terminal ([Who Records](#who-records)). Planned: the `target` a mirror was
opened at (its web URL, which waits for `ProviderUrlReducer.web_url` in
jlevy/metabrowser#540), a folder’s root resolved to its repository’s (`mb-2wfk`), and a
route for a switcher in the page, in the
[native macOS app plan](../specs/active/plan-2026-11-10-native-macos-app.md#phase-4-recent-targets-the-switcher-and-the-mcp-adapter).
The modes, roots, and views are those of [Open Modes](arch-open-modes.md).

Metabrowser keeps one list of what the user opened lately, and every shell reads it
through `metab`: the command line, the macOS app, and any later shell.
A shell draws the list and never decides what is in it, so two shells cannot disagree.

Two things with similar names are not this list:

- **The Recent tab** and `/api/recent` list the recently modified files inside one
  served root, from that root’s inventory
  ([views, models, and routes](arch-views-models-routes.md)). Recent targets are the
  roots themselves, across every server.
- **`last_opened_at` in the cache** (`sources/<slug>/state.yml`) is when a cached source
  was last acquired or reused, by a data mode as much as by a reader, and it goes when
  the cache is cleared.
  Recent targets are what a reader opened, in either mode, and outlive the cache.

## Vocabulary

The words are those of [Open Modes](arch-open-modes.md#vocabulary).

- **Target:** what `metab TARGET` is given: a folder, a file, or a URL.
- **Root:** what one server serves, and what the app windows that show it belong to: a
  folder, or a repository’s address.
  A folder’s root is its **open root**, the folder a serve of the path named serves.
- **Mode:** how a root was opened, `folder` or `mirror`. It is fixed while the root is
  open. `folder` is either folder mode, a plain folder or a repository folder, which the
  `mode` writes as one value and the entry’s `git` tells apart; `mirror` is a repository
  opened by its address and read from Metabrowser’s own copy of it.
  The three kinds of root that `kind` in `GET /api/identity` reports, and that a shell
  draws a mark for ([Source Kinds](../../design-system-icons.md#source-kinds)), are the
  mirror, a folder that was a checkout, and any other folder.
- **View:** what a server shows at a given moment, a folder’s working tree or one
  revision. No entry records it.

## The Entry

A recent target is a root, the mode it was opened in, and when, with where the open
pointed when that was not the root:

| Field | Meaning |
| --- | --- |
| `mode` | `folder` or `mirror` |
| `root` | A folder’s open root, its absolute path with symbolic links resolved, or a repository’s credential-free address as the root grammar normalizes it (`GitSource.normalized`) |
| `opened_at` | When it was last opened, in UTC to the second |
| `target` | Optional, and not part of the key: the file or folder named inside a folder’s root, by its absolute path with symbolic links resolved. A mirror’s is to be its web URL. It is always inside the root |
| `git` | Optional, and not part of the key: whether a folder’s root was a checkout when it was opened, that is, held a `.git` entry (`is_checkout_root` in `repository_context.py`), the `git` kind `GET /api/identity` reports for it. Written only when true and only for a folder, listed as `false` when absent. It is what a shell draws a root’s mark from, since a shell never looks at a listed folder ([Folders That Are Gone](#folders-that-are-gone)); an entry from before the field, or of a folder that became a checkout since, is a plain folder until it is opened again |

- **A folder’s root** is the open root `metab` serves for the path named, which one
  function decides for both serving and `--recent-add`: `resolve_local_open` in
  `cli/common.py`. Today that is the folder named, or a file’s folder.
  The open-modes resolver (`mb-2wfk`) replaces that function’s body to open the
  enclosing repository’s root, and the list then records that root, with the path named
  as the `target`.
- **Its spelling** on macOS is the one `realpath(3)` gives (`recorded_path` calls that
  function), so two spellings that differ only in case are one folder, and the root is
  the very string the app names the folder’s session by (`FileChecks.canonicalPath`).
- **A mirror’s root** for a GitHub URL is exactly `https://github.com/<owner>/<repo>` in
  lower case, whatever the URL selected inside the repository: the root
  `metab URL --present --dry-run --json` reports, and the key of the app’s session for
  that repository (`SessionRoot.repository`). Another Git source, such as a `file://`
  clone URL, is its normalized address.
- **The key** is `mode` and `root` together, which is the app’s `SessionRoot` key, so
  one entry is one open root, however many windows show it, and reopening an entry that
  is open brings its window forward.
- **No credential is ever stored.** A root comes from the grammar that refuses a URL
  with a password or token, never from the argument as typed.
- **A root with a control character or a line separator is not recorded.** A terminal
  acts on the first, and YAML reads the second as a line break, which its two emitters
  write differently. Such a folder serves as any other and stays out of the list.
  A `target` the list cannot hold, by the same rules or because it is not inside its
  root, is left out, and the root is recorded without it.
- **No entry records a view.** A recent folder reopens on its working tree, whatever
  revision its window last showed, and its `target` is a path, never a revision.
  A mirror reopens its repository at the default branch, and a pull request is one click
  away on its Pulls tab.
- **A mirror’s `target` is not written yet.** It is to be the web URL the open named,
  rebuilt from what the URL grammar read and never the argument as typed, so it carries
  no credential or query the grammar does not read: `ProviderUrlReducer.web_url`, which
  jlevy/metabrowser#540 adds.
  This release reads and keeps one already.

## The Store

`recent_targets.py` holds the format, the bounds, and their reasons beside the
constants; this section says what they mean.

- **Where.** `recent-targets.yml` in the
  [configuration directory](arch-repository-cache.md#cache-and-configuration-directories),
  beside `config.yml`, with `recent-targets.lock` next to it.
  The owner chose the configuration directory on 2026-11-18. The list is history the
  user would miss, so it does not belong in the cache, which may be deleted at any time,
  and the configuration directory is the durable place `metab` already has.
  `--config-dir`, `METABROWSER_CONFIG_DIR`, and `XDG_CONFIG_HOME` move it with the
  configuration.
- **Private.** The list names the user’s folders and repositories, so it is read and
  written only through `home.py`’s owner-only helpers: a configuration directory another
  account can read or redirect is refused, and the file is published with
  `write_private_file_atomic`.
- **YAML.** One mapping with a `format` and the `targets`, in order, so a person can
  read the file, as they can `config.yml`. It is read with PyYAML’s base loader, which
  makes every scalar a string and constructs nothing, and not with the schema library
  the cache’s records use, which a folder’s server never loads.
  `metab --recent --json` still answers in JSON.
- **The format string** follows the application home’s convention
  ([Layout](arch-repository-cache.md#layout), on `layout.yml`): a short string that says
  what it is, an append-only `FORMAT_HISTORY`, a `MIGRATIONS` step from each format to
  the next, and a refusal of a format newer than the release reads.
  Metabrowser’s format strings are `mf` and a number, to tell them from tbd’s `fNN`;
  this file is the first to use the spelling, and moving `layout.yml` and `config.yml`
  to it is `mb-3x6y`. One change is compatible and keeps the string: a new field on an
  entry. A reader that does not know a field keeps it on every entry it carries through a
  rewrite, and drops it only from the entry it records again, whose new open the field
  no longer describes.
  Anything else new raises the number: a mode, a key beside `format` and `targets`, or a
  relaxed rule. A file from a newer release is left exactly as it is: this release lists
  nothing, records nothing, and says to upgrade.
  So is a well-formed file with a mode or a key this release does not know, whatever
  format it names, so a release that forgot to raise the number costs no list.
- **Order.** Most recently opened first.
  The position in the file is the order; `opened_at` is for display.
- **One entry per root.** Opening a root again moves its entry to the front.
- **Bounded.** `MAX_RECENT_TARGETS` caps the list, and the oldest entry falls off.
  `MAX_ROOT_BYTES` and `MAX_STORE_BYTES` bound one root and the file, and a writer reads
  back what it is about to publish, so it never publishes a file a reader would refuse.
- **A damaged file is replaced.** A file that is not this format, an entry that breaks
  the rules above, or a file over the bound lists as empty with the reason, and the next
  record, forget, or clear writes a fresh list.
  Nothing else depends on the list, so losing it costs only the list.

### Folders That Are Gone

Listing never looks at a listed folder, and nothing prunes on a timer.

- **A look can prompt.** On macOS, touching a folder in Desktop, Documents, Downloads,
  or cloud storage can raise a privacy prompt in the app’s name, and the app’s rule is
  that no prompt appears for a folder nobody asked to see
  ([session restore](arch-macos-app.md#session-restore)).
- **A look can hang.** A path on a network volume that is not answering blocks the
  process that asks.
- **Gone is often temporary.** A drive is unplugged, or a worktree is removed and made
  again.

So an entry stays until one of three things removes it: newer entries push it past the
cap, the user forgets it or clears the list, or the user opens it and it is gone, when
the shell says so and forgets it.

### Concurrent Writers

The writers are `metab` processes: every server that records
([Who Records](#who-records)) as it starts, and the modes below.
The app writes nothing itself.

- A writer takes an exclusive `flock` on `recent-targets.lock`, reads the list, changes
  it, publishes it by atomic rename, and releases the lock.
  Two servers starting at once therefore both end up in the list.
- A reader takes no lock: a rename shows it the old file or the new.
- The lock is tried without blocking for at most `LOCK_WAIT_S`. A record that cannot
  take it, or that fails for any other reason, is skipped with a logged warning: the
  list is never worth delaying or failing a server for.
- A holder that dies releases its lock at once, as the kernel closes its descriptor, so
  no stale lock outlives a crash.

## What Records

| Opened by | Records | How |
| --- | --- | --- |
| `metab FOLDER` or `metab FILE` run at a terminal | `folder`, the served folder, with a file or `--path` as its `target` | `serve_until_interrupted`, just before the `Serving` line, when `serve_records` says yes: its stdin is a terminal |
| `metab URL` run at a terminal | `mirror`, the source’s address | The same, once the source is acquired and its pin resolved |
| `metab ROOT` run by an agent, a test, a golden, a script, or a tool | Nothing | Its stdin is a pipe or `/dev/null`, not a terminal, and nothing set `METABROWSER_RECORD_RECENT=1` ([Who Records](#who-records)) |
| The macOS app opening a folder, open already or not, or showing an open one chosen in a window’s title menu or the Switch Folder panel | `folder` | `metab FOLDER --recent-add`, as the app shows it (`AppDelegate.showOpened`, `RecentTargetsMenu.shown`) |
| The macOS app opening a GitHub link, Open URL…, or a recent repository | `mirror` | `metab ROOT --recent-add` with the repository’s canonical address, as the app shows it, whether a server starts for it or a running one opens the link |
| Any server the macOS app starts | Nothing | The app records the open itself, so it tells every server `METABROWSER_RECORD_RECENT=0` (`RecentTargets.serverRecords`, `FolderServer`) |
| `metab ROOT --present` handed to the app | As the app’s open of it, above | `open -b` hands the app a path or a link, as Finder does, so the app records it whoever ran `--present`: an agent’s presented folder is listed (see below) |
| `metab ROOT --present` served for a browser | As `--present` would record itself | `serve_detached` gives the server it starts `METABROWSER_RECORD_RECENT=1` when `serve_records` says yes for `--present`, and `0` otherwise |
| The app restoring its last session, a Dock click with no window, a page’s link opening another window of its folder, Command-R, Retry, Restart Server, or an upgrade’s restart | Nothing | None of them is an open, so none comes through `showOpened`, and their servers record nothing. The restore and a Dock click report what they show as `restored` and `reopenedFromTheDock`, for which `RecentTargets.changes` makes no change |
| Anything a development build started by `make macos-run` opens | Nothing | `make macos-run` starts the app with `METABROWSER_RECORD_RECENT=0`, which the app passes on to every `metab` it runs, its `--recent-add` included |
| Anything an app started with `METABROWSER_CONFIG_DIR` opens | Into that directory’s list, not the user’s | The app passes the variable on to every `metab` it runs (`ChildEnvironment`), the `--recent-add` that records an open and the `--recent` that lists the menu included; the [hand checks](../qa/qa-macos-app-hand-checks.md) launch a development build this way |
| `metab --remote HOST --path DIR` | Nothing, on either host | The near side serves nothing, and the far server is started with `METABROWSER_RECORD_RECENT=0` (`cli/remote.py`): that account did not open the folder to read it there |

A root is recorded before its server’s `Serving` line, so whoever reads that line finds
the root already listed.
`--api`, `--show`, `--walk`, `--diff`, `--check-api`, and `--no-serve` open nothing for
a reader and record nothing.
A server that fails before that point records nothing, so a mistyped path never enters
the list.

**The order changes only when the user opens something**, which the owner decided on
2026-11-18: Open Folder…, Open URL…, Open Recent, a drop, or `metab` run in Terminal.
In the app, every open comes through `AppDelegate.showOpened`, which records it once, as
it shows it, and no server the app starts records (mb-1q02). The app’s records run one
at a time, in the order they were made (`RecentTargets.Changes`), so of two opens in
quick succession the later is listed first; one made while no `metab` may run waits
until one may.
An open is recorded whether or not its server then starts, as the user did
open it: a folder the app refuses, one that is not a folder or cannot be served, is
never shown and never recorded, but a repository whose first clone fails is listed until
it is forgotten.

### Who Records

The list is the user’s own opens, so a serve records only when someone opened it to
read, which `metab` can tell in two ways (`serve_records` in `recent_targets.py`):

- **It is told to.** `METABROWSER_RECORD_RECENT=1` (`RECORD_ENV`) makes a serve record.
  `--present` sets it on the server it starts for a browser when it would record itself,
  and a script that should record what it serves can set it too.
  The macOS app needs neither: it records each open itself with `--recent-add`, and
  tells every server it starts `0`.
- **A person typed it.** With the variable unset, a serve records only when its stdin is
  a terminal. A serve an agent, a test, a golden, `check_parity`, or any other tool
  starts reads a pipe or `/dev/null` there, so it records nothing, and nobody has to
  remember to turn recording off.

`METABROWSER_RECORD_RECENT=0` keeps any process from recording, a terminal’s too: its
serve records nothing and touches no file, and `--recent-add` records nothing and says
so. `--recent-add` is itself a request to record, so it records unless the variable is
`0`. Listing, forgetting, and clearing always work.

**Why a terminal (`mb-1q02`).** Before this rule every serve recorded, whoever started
it. On 2026-11-24 one user’s list held 47 entries, and 25 of them had been recorded by
serves no app made: by their paths, nearly all were agents’ worktrees, attic and
scratchpad folders, a test fixture folder, and two fixture mirrors.
Seven of the 16 the app’s menus show (`RecentTargets.menuLimit`) were of that kind, and
folders the user had opened the day before sat past the sixteenth.
Every open the app had made since the list began was recorded; the app’s server logs
(`~/Library/Logs/Metabrowser`) showed each open’s start beside its entry.
The serves that pushed them out were made where no person was, and a terminal is what
such a serve lacks, so the rule needs no list of agents and no step a tool must
remember. A tool or a person who wants a serve without a terminal recorded says `1`.

**What it does not catch.**

- A folder an agent presents to the app (`metab ROOT --present`) is listed: `open -b`
  carries only the path or the link, as Finder’s open does, so the app cannot tell it
  from the user’s own.
  Telling it would take a channel the hand-off does not have, such as a URL scheme of
  the app’s own, which would also let any web page ask the app to open a local folder.
  The skill tells agents to present only what the user should see, and to serve what
  only the agent needs.
- An agent that runs `metab ROOT` inside a pseudo-terminal of its own has a terminal,
  and its serve records.

Five things set `0`, for servers nobody opened to read whatever their stdin:

- the app, for every server it starts, since it records each open itself;
- the test run (`tests/conftest.py`), which also points `METABROWSER_CONFIG_DIR` at a
  directory of the run’s own, and of each test’s, so nothing a test runs reads, writes,
  forgets, or clears the list of whoever runs the suite; a test of the record itself
  turns it back on in its own directory;
- `make macos-run`, through `open --env`: agents start the development build this way
  for hand checks, and the app passes its own setting on to every `metab` it runs
  (`ChildEnvironment.passedThrough`), so a development run records nothing at all, what
  the person using it opens included;
- the benchmarks: `devtools/bench_serving.py`, `devtools/compare_builds.py`, the
  performance loop’s harnesses, `explorations/tree-summary-storm/run.sh`, and the WebKit
  gate, which also keeps the write out of the startup they time;
- `metab --remote`, for the server it starts on the far host.

A `.env` file cannot set it, as it cannot set any name outside `metabrowser.dotenv`’s
list.

## The `metab` Modes

| Mode | Does |
| --- | --- |
| `metab --recent` | Lists the entries, most recent first; `--json` prints `{"limit", "targets", "problem"}`, each target with its `mode`, `root`, `opened_at`, `target`, `null` when there is none, and `git` |
| `metab TARGET --recent-add` | Records TARGET as opened, as a serve of it would, without serving: the same root and `target`, by the same `resolve_local_open` |
| `metab TARGET --recent-forget` | Removes TARGET’s entry; a folder that no longer exists is matched by its path as given |
| `metab --recent-clear` | Empties the list |

`tests/golden/cli-recent.tryscript.md` pins all four, the order, one entry per root, a
file’s `target`, a damaged file, a newer format, and a configuration directory that is
not private. `tests/test_recent_targets.py` covers the store itself, the cap and
concurrent writers included, and that a real serve records before it announces itself.

No route serves the list, which the owner confirmed on 2026-11-18. A route would hand
every page of every served root the names of the user’s other folders and repositories,
over a loopback port that asks for no credential, which the switcher’s design has to
settle first.

## The macOS App

File > Open Recent is drawn from `metab --recent --json` (`RecentTargets` in
`ShellCore`, `RecentTargetsMenu` in the app):

- The app runs the selected `metab` when it becomes active, when the menu opens, when
  the Dock menu is asked for, and after each change it makes to the list, an open’s, a
  forget, or a clear, once every change asked for before it has run
  (`RecentTargetsMenu`), so the next Dock menu lists that open.
  A menu shows the last answer at once, then the new one.
- Every `metab` the app runs has the modes: setup’s check runs with `--recent`
  (`MetabRequirement.requiredFlags`), so a build from before the list is refused with
  the upgrade it needs, as one from before `--exit-on-eof` is.
- It lists every entry it can open: folders, and repositories once the build opens
  links, which its `Info.plist` says with `MetabrowserOpensURLs`.
- **Both menus show the 16 most recent** of those, `RecentTargets.menuLimit`, and the
  folder chooser’s Recent section the 16 most recent that are not open; the list keeps
  `MAX_RECENT_TARGETS`, so an entry past the sixteenth is still in `metab --recent`.
- **Every way the user opens a folder or a repository in the app is shown by
  `AppDelegate.showOpened`, which records it once**, at the open
  (`RecentTargetsMenu.shown`, `metab ROOT --recent-add`): File > Open Folder…, a drop on
  the Dock icon or a page, Open With, `open -a`, a folder `--present` hands over, Open
  Recent, the Dock menu, Open URL…, a GitHub link sent to the app, and the folder
  chooser and Switch Folder panel, an open folder chosen there included.
  A GitHub link sent into a repository that has a window opens in that window’s server
  without `showOpened`, and records with the same call.
  Help > Open Event Log opens its directory as `openedForTheApp`, which records nothing.
  No server the app starts records (`RecentTargets.serverRecords`).
- **The restore and a Dock click record nothing.** The windows a launch restores and the
  folder a Dock click with no window brings forward are reported as `restored` and
  `reopenedFromTheDock`, and `RecentTargets.changes` makes one `--recent-add` for an
  open and none for anything else, which `RecentTargetsTests` pins.
- The legacy `recentFolders` key some builds’ defaults domains still hold is the spike’s
  list, which no build has read since the app moved to macOS’s list and then to this
  one; nothing reads it, and nothing needs to remove it.
- Titles come from the root, as a window is titled before its server answers
  (`FolderIdentity`), and no listed folder is touched to draw the menu.
- Clear Menu runs `metab --recent-clear`. Choosing a folder that is gone shows the app’s
  usual message and runs `metab FOLDER --recent-forget`.
- **The Dock icon’s menu lists the same targets**, in the same order, which the owner
  decided on 2026-11-18: `applicationDockMenu` draws it from the answer File > Open
  Recent is drawn from (`RecentTargets.rows`), without Clear Menu.
  The Dock takes a copy of the menu, so it shows the list as the app last read it, and
  only while the app runs.
  The app no longer registers folders with `NSDocumentController`, which would add
  macOS’s own list beside this one, and clears at launch what an earlier build
  registered.

The app sets no storage override for the `metab` it runs, and passes on the
`METABROWSER_CONFIG_DIR` it was started with (`ChildEnvironment`), so the list it reads
is the one its `--recent-add` writes.
Started from Finder or the Dock, with none, that is the default list, which a person’s
`metab` in Terminal writes too; a development build the hand checks start with a scratch
directory keeps its own list there.
The menu’s contents are `metab`’s, pinned by the golden above; drawing them is AppKit’s,
which the [parity registry](arch-parity-registry.md) records as `app.open-recent-menu`.
`RecentTargetsTests` covers how the app reads the answer and chooses its rows, and
`LiveMetabTests` runs both against a real `metab`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
