# Architecture: Recent Targets

**Status:** Built (`mb-40k4`): the store (`src/metabrowser/recent_targets.py`), its four
`metab` modes (`cli/recent_cli.py`), the record every serve makes, and the macOS app’s
File > Open Recent, which lists what `metab --recent --json` answers.
Planned: the `target` a mirror was opened at (a pull request, a ref, or a commit), a
route for a switcher in the page, and the open-mode indicator, in the
[native macOS app plan](../specs/active/plan-2026-11-10-native-macos-app.md#phase-4-recent-targets-the-switcher-and-the-mcp-adapter)
and the
[mirror and checkout plan](../specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md#open-modes).

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

- **Target:** what `metab TARGET` is given: a folder, a file, or a URL.
- **Root:** what one server serves, and what one app window or tab group belongs to: a
  folder, or a repository.
  `metab FILE` serves the file’s folder, so a file’s root is its folder.
- **Mode:** how a root is open, which is the kind of
  [subject](arch-source-sessions-and-pins.md#subjects) its server holds and the `kind`
  `GET /api/identity` reports.
  `folder` is an attached folder, the user’s own files as they are now.
  `mirror` is a pinned revision of Metabrowser’s own cached copy of a repository.
  [Open Modes](../specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md#open-modes)
  says how a target reaches each mode and what differs between them.

## The Entry

A recent target is a root and the mode it was opened in:

| Field | Meaning |
| --- | --- |
| `mode` | `folder` or `mirror` |
| `root` | A folder’s absolute path with symbolic links resolved, or a repository’s credential-free address as the root grammar normalizes it (`GitSource.normalized`) |
| `opened_at` | When it was last opened, in UTC to the second |

- **A folder’s root** is the path the server serves (`run_serve`), spelled on macOS as
  the volume spells it (`folder_root`), so two spellings that differ only in case are
  one folder, as they are to the app, which names a folder by `realpath(3)`.
- **A mirror’s root** for a GitHub URL is exactly `https://github.com/<owner>/<repo>` in
  lower case, whatever the URL selected inside the repository: the root
  `metab URL --present --dry-run --json` reports, and the key of the app’s session for
  that repository (`SessionRoot.repository`). Another Git source, such as a `file://`
  clone URL, is its normalized address.
- **The key** is `mode` and `root` together, which is the app’s `SessionRoot` key, so
  one entry is one window or tab group, and reopening an entry that is open brings its
  window forward.
- **No credential is ever stored.** A root comes from the grammar that refuses a URL
  with a password or token, never from the argument as typed.
- **A root with a control character or a line separator is not recorded.** A terminal
  acts on the first, and YAML reads the second as a line break, which its two emitters
  write differently. Such a folder serves as any other and stays out of the list.
- **What a mirror was pinned to is not recorded yet.** An entry reopens its repository
  at the default branch, and a pull request is one click away on its Pulls tab.
  Recording the `target` is planned with File > Open URL….

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
  to it is `mb-3x6y`. The number rises only for a change an older reader would misread,
  and a compatible change keeps it.
  A file from a newer release is left exactly as it is: this release lists nothing,
  records nothing, and says to upgrade.
- **Order.** Most recently opened first.
  The position in the file is the order; `opened_at` is for display.
- **One entry per root.** Opening a root again moves its entry to the front.
- **Bounded.** `MAX_RECENT_TARGETS` caps the list, and the oldest entry falls off.
  `MAX_ROOT_BYTES` and `MAX_STORE_BYTES` bound one root and the file, and a writer reads
  back what it is about to publish, so it never publishes a file a reader would refuse.
- **A damaged file is replaced.** A file that is not this format, an entry that breaks
  the rules above, or a file over the bound lists as empty with the reason, and the next
  record writes a fresh list.
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

The writers are `metab` processes: every server as it starts, and the modes below.
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
| `metab FOLDER` or `metab FILE` | `folder`, the served folder | `serve_until_interrupted`, just before the `Serving` line |
| `metab URL` | `mirror`, the source’s address | The same, once the source is acquired and its pin resolved |
| The macOS app opening a folder | `folder` | The server the app starts is `metab FOLDER`, so the line above does it |
| The app showing a folder that is already open | `folder` | `metab FOLDER --recent-add`, because no server starts |
| The app restoring its last session | `folder`, as each restored server starts | The first line again; a tab that waits for its selection is not recorded until then |

A root is recorded before its server’s `Serving` line, so whoever reads that line finds
the root already listed.
`--api`, `--show`, `--walk`, `--diff`, `--check-api`, and `--no-serve` open nothing for
a reader and record nothing.
A server that fails before that point records nothing, so a mistyped path never enters
the list.

## The `metab` Modes

| Mode | Does |
| --- | --- |
| `metab --recent` | Lists the entries, most recent first; `--json` prints `{"limit", "targets", "problem"}` |
| `metab TARGET --recent-add` | Records TARGET as opened, as a serve of it would, without serving |
| `metab TARGET --recent-forget` | Removes TARGET’s entry; a folder that no longer exists is matched by its path as given |
| `metab --recent-clear` | Empties the list |

`tests/golden/cli-recent.tryscript.md` pins all four, the order, one entry per root, a
damaged file, a newer format, and a configuration directory that is not private.
`tests/test_recent_targets.py` covers the store itself, the cap and concurrent writers
included, and that a real serve records before it announces itself.

No route serves the list, which the owner confirmed on 2026-11-18. A route would hand
every page of every served root the names of the user’s other folders and repositories,
over a loopback port that asks for no credential, which the switcher’s design has to
settle first.

## The macOS App

File > Open Recent is drawn from `metab --recent --json` (`RecentTargets` in
`ShellCore`, `RecentTargetsMenu` in the app):

- The app runs the selected `metab` when it becomes active and when the menu opens, and
  the menu shows the last answer at once, then the new one.
- It lists every entry it can open: folders, and repositories once the build opens
  links, which its `Info.plist` says with `MetabrowserOpensURLs`.
- Titles come from the root, as a window is titled before its server answers
  (`FolderIdentity`), and no listed folder is touched to draw the menu.
- Clear Menu runs `metab --recent-clear`. Choosing a folder that is gone shows the app’s
  usual message and runs `metab FOLDER --recent-forget`.
- The Dock icon’s menu is macOS’s own: the app still registers each folder it opens with
  `NSDocumentController`, and macOS keeps that list, in its own order and length, for
  each build of the app.

The app does not pass a storage override to the `metab` it runs, so the list it reads is
the one its servers write.
The menu’s contents are `metab`’s, pinned by the golden above; drawing them is AppKit’s,
which the [parity registry](arch-parity-registry.md) records as `app.open-recent-menu`.
`RecentTargetsTests` covers how the app reads the answer and chooses its rows, and
`LiveMetabTests` runs both against a real `metab`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
