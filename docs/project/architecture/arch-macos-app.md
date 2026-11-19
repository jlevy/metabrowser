# Native macOS App Architecture

**Status:** Built: an alpha AppKit and `WKWebView` shell in `apps/macos/`, built from
source. `.github/workflows/macos-app.yml` builds and tests it on each push and pull
request that its path filter matches, a change to the app among them; its release
pipeline has run only with an ad hoc signature.
Planned: host mode, the agent front door, a signed and notarized release, and updates,
in the [native macOS app plan](../specs/active/plan-2026-11-10-native-macos-app.md).
The WebKit measurement gate failed on 2026-11-11 (`mb-gvtw`), and its rerun is open
(`mb-76nv`).

The app finds a command-line install of `metab`, starts one server per folder or GitHub
repository the user opens, and shows each in a native window or tab.
Everything a window shows comes from that server: the page talks to it over HTTP and
server-sent events and never calls into the app, so any shell can replace another.
The app adds what a browser tab cannot: a Dock icon, folders opened with Open With or
dropped on it, native menus, windows, and tabs, a session that comes back at the next
launch, and server lifetimes it controls.
[Using the app](../../macos-app.md) is a user guide, and building, testing, and
releasing it is [the app’s README](../../../apps/macos/README.md).

## Modules

Paths are under `apps/macos/`.

| Path | Holds |
| --- | --- |
| `Sources/ShellCore/Supervision/` | Spawning a server, what it says as it starts, recognizing it as ready, checking its health, and stopping it |
| `Sources/ShellCore/Runtime/` | Finding `metab`, settling which one runs, and the child environment |
| `Sources/ShellCore/Setup/` | The version floor, the first-run steps, file watches, the restart offer after an upgrade, and the launch notice |
| `Sources/ShellCore/Logs/`, `Folders/`, `Web/` | Server logs; folder identity, titles, files opened inside folders, GitHub links, their failures, and File > Open URL…, tab placement, and the saved session; the navigation policy, web view configuration, tab discards, reloads, and downloads |
| `Sources/ShellCore/App/` | Which build is running (`AppIdentity`), and the title-bar mark |
| `Sources/ShellViews/` | `DropAwareWebView` and `WebContainerView`, a library of their own so that the WebKit gate’s driver builds the same views |
| `Sources/Metabrowser/` | The AppKit app: lifecycle, menus, folder sessions, windows, and the SwiftUI status and settings views |
| `webkit-gate/` | The WebKit measurement gate and its driver, which no product ships |

`ShellCore` holds every decision that can be tested without a window, and imports no
AppKit; it imports WebKit only for the web view’s configuration and downloads, which its
tests run in a windowless `WKWebView`. The app target connects those decisions to AppKit
and WebKit. It is the platform behavior the
[packaging brief](../research/research-2026-11-08-macos-app-packaging.md) exempts from
the [parity rule](../../../AGENTS.md#cli-and-functional-ui-parity): finding a runtime
before one exists, windows, menus, the Dock, and file events.

## A Server per Folder

1. **Open.** File > Open Folder…, Open Recent, the Dock menu, a drop, Open With,
   `open -a`, and the restore all reach one `FolderSession` per folder, keyed by its
   canonical path, so a root has one server however many windows and tabs show it.
   That path is also the folder’s key among the
   [recent targets](arch-recent-targets.md).
   [Open Modes](arch-open-modes.md#what-keys-on-the-root) designs that key as the open
   root `metab` resolves, which for a path inside a repository is the repository’s root.
   A GitHub link, sent to the app or typed into File > Open URL…, reaches one per
   repository, keyed by its canonical URL ([GitHub Links](#github-links)); `SessionRoot`
   names both.
2. **Spawn.** `ServerSupervisor` runs `CLIServeLaunch`’s command,
   `metab ROOT --no-open --exit-on-eof --host 127.0.0.1 --port N`, from its lane’s
   `LaunchLane.basePort` (`SessionRoot.lane`). `SpawnedProcess` starts it with
   `posix_spawn` in its own process group, with only the descriptors it names, default
   signal handling, and the folder as its working directory, so `.env` lookup matches
   `metab .` in Terminal (a repository’s server runs in the home folder, as `metab URL`
   in a new Terminal window does).
   Its stderr is the server log itself, so an app that stalls cannot block it on a full
   pipe; its stdout is a pipe the app reads for the announcement and appends to the log;
   and its stdin is a pipe the app holds open.
3. **Ready.** The server prints `Serving ROOT at URL` before its socket listens, so the
   supervisor parses that line (`CLIServeLaunch.parseServingLine`) and polls the URL for
   a 2xx (`HTTPReadiness`) before its `StartupDeadline`: for a folder,
   `SupervisorPolicy.startupTimeout` from the spawn.
   A root whose path holds a line break is refused, since its name could forge the line.
   A `LaunchGate` lets one server start at a time, because `metab` picks its port by
   probing and binds it later.
   The app holds two, one for folders and one for repositories, whose port walks start
   apart (`CLIServeLaunch.repositoryBasePort`, past every port a folder’s walk reaches),
   so a first clone holds up no folder.
4. **Show.** The window’s `WKWebView` uses the persistent default data store
   (`WebConfiguration.make`), since Metabrowser keeps preferences in host-only cookies.
   A status view covers it until the page commits, and only the navigation the window
   submitted last can reveal the page (`PageReveal`), so a late commit cannot hide a
   server’s failure.
5. **Check.** A window that joins a running server first asks for the entry page within
   `SupervisorPolicy.healthDeadline`, since a hung server keeps its pid; one that does
   not answer is stopped, and fails.
6. **Fail.** Every window of the folder shows the reason, the last lines of output, and
   Retry. Nothing restarts by itself, except a repository whose start failed on GitHub,
   when the app becomes active ([GitHub Links](#github-links)); after Retry, each window
   returns to its page on the new port.
7. **Stop.** Closing a folder’s last window stops its server: SIGTERM to the process
   group, `SupervisorPolicy.shutdownGrace`, SIGKILL, `killWait`, then SIGKILL to
   anything left in the group.
   The leader is reaped only after that, so its pid, which is the group’s id, cannot
   pass to another process while signals are still sent.

Every child is ended by one tracked termination (`ServerSupervisor.retire`), whoever
asks. Each launch and stop advances a generation, so work for an older one stops, and a
folder whose last window closed is shut down for good, so closing it during a restart
leaves nothing running.
`ServerFleet` holds the open and still-stopping servers, and quitting waits for all of
them, also on SIGTERM, SIGINT, or SIGHUP (`AppDelegate.installTerminationSignals`).

`metab ROOT --present` reaches the app the way `open -a` does: it asks LaunchServices
for the bundle and sends the paths or URL with `open -b`
([Presenting to the App](arch-cli.md#presenting-to-the-app)). A file named alone arrives
alone, and `AppDelegate.request` places it with `OpenTarget.resolve` as it places any
file; a file `--path` names arrives after its ROOT, in one `application(_:open:)` call,
so `request` opens the root first and then places the file in the most specific open
folder, which is that root unless a folder inside it holding the file is open.
It sends only to a bundle at one of `APP_INSTALL_LOCATIONS` whose `Info.plist` names it
Metabrowser and sets `MetabrowserOpensURLs` to true, so a build that cannot yet open a
URL, a build registered where it was built, or another app receives nothing, and it
learns nothing back.

`ServerLaunch` is the seam for host mode: it owns the arguments, the stdin line, the
readiness parser and URL, and what a window installs before loading
(`WebAuthorization`), so a host-mode launch replaces `CLIServeLaunch` without changing
the supervisor or the windows.

Each folder’s server writes `<folder>-<hash>.log` in `AppIdentity.logsDirectory`, which
both variants share, with the app’s lifecycle events between its lines (`ServerLog`); a
repository’s is named for the repository, with the hash of its URL. A launch claims its
log before it spawns (`FolderLog`, `ServerLogLease`), so a second running copy of the
app, or an earlier session still stopping, writes a log of its own.

### GitHub Links

A link reaches `application(_:open:)` from `open -b`, which is how `metab URL --present`
sends one; the app does not register for `https`, which browsers own.
`AppDelegate.requestLink` takes an `https` link on a host of `metab`’s GitHub reducer
(`GitHubLink`) and reads nothing else of it.
Links wait in a `LinkQueue` and are resolved one at a time: each runs
`metab LINK --present --dry-run --format json` (`PresentDryRun`), which clones and
fetches nothing, and the app acts on the answer (`PresentAnswer`):

| Answer | What the app does |
| --- | --- |
| Exit 0 with `kind`, `root`, and `handoff` | Opens `root`’s session on `handoff` |
| A nonzero exit with a `refusal` | Shows `refusal.message`, which names the fix |
| Anything else | Shows the reason and the command’s last lines |

The command’s stdout and stderr share one pipe, so the answer is the one JSON object
among its lines (`JSONAnswer`); two candidates are refused, since a line on stderr could
otherwise stand in for the answer, and a block from a `{` line to a `}` line that does
not parse counts as one, so a stray `{` that swallows the real answer leaves nothing a
later line could stand in for.
A plan’s `kind` must be one a link resolves to, its `root` a canonical
`https://github.com/<owner>/<repo>` (`PresentPlan.repositoryURL`), and its `handoff` one
link into that repository on `github.com` that `GitHubLink` accepts.
The plan’s `page` is not read: it is null where only the mirror knows where a ref ends,
and the server, which resolves the link against its mirror, announces the right page.

- **Which session.** The repository’s canonical URL keys its session
  (`SessionRoot.repository`), never the pin, which a page can switch while the server
  runs, as [Open Modes](arch-open-modes.md#what-keys-on-the-root) has it.
  A new session starts `metab HANDOFF`, so `metab` pins what the link selects and reads
  a pull request it names, and its window loads the entry page the server announces;
  Retry and Restart Server run the session’s latest link again.
- **A link into an open repository.** The window may show another branch, commit, or
  pull request’s head than the link names, and the app cannot tell, since the dry run
  reports no ref, so it never only navigates: `FolderSession.open(link:)` starts the
  server again on the link, and the front window loads the new entry page
  (`NextPage.requestEntry`), as the owner decided on 2026-11-17 and
  [Open Modes](arch-open-modes.md#the-file-menu) states for Open URL…. What a link does
  to the session is `RepositoryLinks`, a table of the link, the server’s state, and the
  link it starts on: a start under way runs to its end first, so a first clone is not
  thrown away, and the newest link sent meanwhile waits for it; the link that start
  already runs on joins it, so sending a link twice during its first clone clones once
  and does not restart, and the window still loads that start’s entry page, the link’s,
  whoever began the start (Retry, Restart Server, and an upgrade’s restart run on the
  same link); a failed or stopped server starts again at once.
  A restart of a ready server waits for the launch gate before it stops anything
  (`ServerSupervisor.restart`), so while another repository’s first clone holds the gate
  the repository’s other tabs go on with the old server, and the window that asked for
  the restart says it waits instead of showing the old revision (`RestartWait`): the
  window a link brought forward, the one File > Restart Server was chosen in, or the
  front window for an upgrade’s restart.
  The supervisor reports only its first waiter (`onGateWait`), so a restart asked for
  while another waits shows its window at once.
  The pin switch View on branch makes (`POST /api/source/pin`) would keep the port and
  the server, but it takes a ref or a commit, which the app does not have for a link
  whose ref holds a `/`.
- **A selection the mirror lacks.** `metab` serves a link whose branch, tag, or commit
  its mirror does not have yet from the default branch, and fetches once; the page goes
  to the link’s address by itself if the fetch finds it.
  So the windows can show the default branch for as long as that fetch runs, which the
  page’s fetch chip says.
  After each start of a repository’s server the app asks `/api/source/status` while its
  `selection_state` is `pending` (`LinkSelection`), and says in an alert when the fetch
  did not find the link’s selection (`not_found`) or could not run (`fetch_failed`),
  naming the revision the windows show instead.
- **Asking before a clone.** A link that would start a new session asks first unless
  `metab`’s cache holds the repository (`RepositoryCache`), which the app learns from
  `metab FOLDER --api /api/cache/sources --format json`, page by page, run in the app’s
  support folder; a published source whose `identity.display_url` is the root, with no
  problems, is one `metab URL` serves from without cloning.
  An answer it cannot read asks; `tests/test_macos_app_pins.py` holds the keys and the
  value the app reads to what the route prints.
  The confirmation names the repository and says that it clones and reads with the
  user’s `gh` sign-in, as the owner decided on 2026-11-17; Cancel is its default button,
  so a Return typed into another app as this one comes forward declines.
  The question waits beside the link queue, not in it (`CloneQuestions`): links behind
  it, into open repositories among them, go on resolving, and links into the same
  repository wait for the one answer, which opens the newest of them.
  A repository found or agreed to is not asked about again while the app runs; one
  declined is not asked about again until the burst ends, and the links it turned away
  are counted in the burst’s alert.
- **A burst.** One `metab` resolves at a time, a link equal to one waiting or being
  resolved is dropped, and past `LinkQueue.limit` waiting links the rest are counted, as
  are links past `CloneQuestions.limit` repositories waiting for a question and past
  `LinkQueue.limit` links waiting for a runtime (`RuntimeSelection.setupForOpening`).
  The links that could not be opened are said in one alert once the burst has ended,
  which keeps the first `LinkAlert.shownInBatch` and counts the rest (`LinkProblems`).
  Its title counts links, not the problems it lists (`LinkAlert.links`): a decline
  stands for every link it turned away, and a link whose selection the mirror lacked did
  open, so the title counts it apart, as a link whose selection was not shown.
  One modal shows at a time, a clone question or that alert, and what gathers while one
  is up is said when it closes.
  A link under way counts as something about to show, so the app does not offer the Open
  panel meanwhile.
- **The first clone.** A repository’s start is given up on only once its output stops
  growing for `SupervisorPolicy.startupTimeout`, or at
  `SupervisorPolicy.repositoryStartupLimit` after its spawn (`StartupDeadline`). Output
  is `ServerProcess.outputProgress`, which counts the log’s growth, since stderr goes
  there without passing through the app.
  `metab` writes a line of a clone’s progress at least every
  `MetabAcquisition.progressLineInterval` when stderr is not a terminal, and the limit
  outlasts its own bound on acquiring a source (`MetabAcquisition.reservationWait`);
  `tests/test_macos_app_pins.py` pins each copied constant to its Python definition in
  the CI jobs that run on every change.
  A start waiting on another process’s acquisition of the same source writes one note
  and then nothing, so it is given up on after `startupTimeout`.
- **Progress.** While a repository’s server starts, its windows show the newest line of
  `metab`’s clone report (`StartProgress`): where the clone goes, how far it has got,
  that it is done, that the cache held it, or that `metab` is reading the pull request
  the link names. The supervisor reads the log’s newest lines each
  `SupervisorPolicy.progressInterval` that the output grew
  (`ServerSupervisor.startProgress`), which for a clone is once per
  `MetabAcquisition.progressLineInterval`, and only for a start with a `startupLimit`;
  what a line means is the launch’s (`ServerLaunch.startProgress(in:)`). The lines are
  `metab`’s words around Git’s numbers, never text Git or the origin wrote, so the
  window shows them as written, less the repository’s URL.
- **A failure on GitHub.** A start that fails ends with `metab`’s `Error:` line, and
  when that line names a state of reaching or reading GitHub (`GitHubFailure.kinds`),
  the windows say which it is: the repository was not found or its account cannot read
  it (`not_found_or_private`); the same with no GitHub CLI found, which the provider’s
  hint to install it marks, so the window names both causes; the connection failed;
  GitHub is limiting requests (`rate_limited`); or GitHub answered with an error
  (`server_error`). The table also maps the GitHub plugin’s `not_logged_in` and
  `gh_missing`, which no start names yet: the plugin’s messages carry no state and reach
  no start’s `Error:` line, so the Swift samples of both are placeholders until the
  status check (`mb-si2g`) decides how a start reports them.
  They show `metab`’s message, the `gh` commands that fix it or show what is wrong, each
  with Copy, as the first-run steps do, and Retry; Copy Message copies the failure, the
  message, and the commands together.
  Any other failure, `too_large` among them, shows its summary and the server’s output.
  `tests/test_macos_app_pins.py` holds the states the app maps, and the lines its tests
  diagnose, to what `metab` prints.
  A clone cannot tell a signed-out `gh`, an account without access, or a sign-in without
  the `repo` scope from a repository that does not exist, since GitHub answers all four
  alike, so today each is `not_found_or_private`, and its steps start with
  `gh auth status`. Telling them apart is the GitHub status check’s (`mb-si2g`).
- **Back from Terminal.** When the app becomes active, each repository whose server
  failed in a way a sign-in in Terminal can fix starts again, as Retry does: GitHub
  showed no repository while `gh` was found (`GitHubFailure.Kind.rechecksOnActivation`,
  `ServerFailure.rechecksOnActivation`, `FolderSession.recheckAfterActivation`), so the
  sign-in clears the failure once the user switches back, and only then does the window
  say it tries again. Nothing else changes: a folder, a server that is ready or starting,
  and every other failure wait for Retry.
  A network failure can come minutes into a first clone’s fetch (`timed_out`), which a
  retry would start again from zero while holding the repository launch gate; a rate
  limit asks for fewer requests; a server error is GitHub’s to fix; and without `gh`
  nothing changes until Find Again, which restarts nothing.
  The recheck runs the start again, since no route reports the sign-in yet, so each
  switch back to the app while a not-found failure stands costs GitHub that failure’s
  requests: the provider’s size check, when `gh` is found, and the probe of the origin,
  which `REMOTE_PROBE_TIMEOUT_S` in `src/metabrowser/cache/origin.py` bounds and whose
  comment holds its measurement; the not-found answer comes from those, before any
  object is fetched. Reading the sign-in instead, and rechecking without a start, is
  `mb-1rl3`’s, once the status check (`mb-si2g`) reports it.
- **Titles.** Until the server answers `/api/identity`, the window is named for the
  repository (`FolderIdentity.repository`), a cached mirror.
  Only a local folder’s window gets a path menu, whatever identity its port answers.
- **Not restored.** `FolderWindows.snapshot` leaves a repository’s tabs out of the saved
  session, whose roots are paths that the restore admits again (`RootAdmission`); a tab
  group whose shown tab is a repository’s is saved showing its first folder tab.
- **The version floor.** `RuntimeDiscovery.validate` probes `--present` with
  `--exit-on-eof`, so a `metab` without it is too old at setup
  ([The Version Floor](#the-version-floor)).

#### File > Open URL…

File > Open URL…, Command-L, shows `OpenURLWindowController`, a panel with one field.
What the panel accepts, says, and does is `OpenURLPanel`, in `ShellCore`; the window
only shows its state and passes on edits, Open, and Cancel.

- **The text is checked first.** `OpenURLEntry` hands `metab` only a link `GitHubLink`
  accepts, the check every link sent to the app passes.
  `metab TARGET --present --dry-run` reads a target with no scheme as a local path, so a
  shorthand such as `owner/repo` would name a folder under its working directory: the
  panel takes none, as the owner decided on 2026-11-18, and asks for the full URL. Its
  other messages, for a scheme other than `https`, a user name or password, a port,
  another host, and a character it does not send, are the app’s own words about what was
  typed; `metab` would refuse each of those too.
- **Sent as a browser sends it.** The scheme and host are checked as typed.
  The path, query, and fragment are then encoded as a browser sends them, each as UTF-8
  escapes: a space and a character outside ASCII that shows, as `metab`’s GitHub reducer
  encodes them (`_browser_encoded`), and an ASCII character a URL cannot hold raw, such
  as `"` or `{`, which `metab` takes raw and encodes in its handoff.
  So a file named `Design Notes.md` or `café.md` opens as `metab URL` opens it.
  A control character, a backslash, a `%` that begins no escape, and a character that
  may not show, such as U+3164 HANGUL FILLER, are refused, as `metab` refuses them.
  `LiveMetabTests` gives `metab` both the text as typed and the link the panel sends,
  and expects one plan.
- **`metab` decides.** Open runs the dry run `resolveLink` runs (`askMetab`), outside
  the link queue, so that a refusal is said in the panel and not in the alert that ends
  a burst. A plan closes the panel and goes to `open(_:with:)`, so from there it is a
  link sent to the app: the question before a clone, one window per repository, and
  always the mirror, never a checkout.
  A refusal shows `refusal.message`; an answer the app cannot read names the `metab` and
  the reason, never its output, which goes to the app’s log.
  Either way the panel stays open with the text.
- **One dry run at a time.** An edit, Cancel, or closing the panel drops the answer
  still awaited, and the app cancels the task that awaits it
  (`stopCheckingEnteredLink`), which kills the dry run’s process group at once
  (`CommandRunner.finish`). So the panel has at most one `metab` running, and Open,
  enabled again by the edit, starts the next.
- **With no `metab` the app can run now,** as while it finds `metab` or checks it again
  after its file changed, the panel closes and the link goes to the link queue
  (`requestLink`), which waits for one as it does for any link: the link is checked once
  `metab` is ready, and a refusal comes as the alert at the end of the burst, not under
  the field.
- **Not built.** The offer of a known checkout, “borrow from the checkout” and “open the
  checkout instead”, which [Open Modes](arch-open-modes.md#the-file-menu) designs, waits
  for a way to tell that an open folder is a checkout of the URL’s repository:
  `GET /api/identity` and a folder’s dry run name no repository (`mb-bkk2`). Filling the
  field from the clipboard, which the owner made optional, is not built.
- **Parity.** What a URL opens is `metab URL --present --dry-run --format json`, the
  [parity registry](arch-parity-registry.md)’s `app.present-resolution` row, whose
  golden pins each kind of link and each refusal code; the panel and its menu item are
  platform behavior, as the app’s other menus are.
  `LiveMetabTests.theOpenURLPanelSaysWhatMetabAnswers` runs the panel against the real
  command.

#### The Trust Boundary

A link is untrusted input: any local process can send the app one, and a web page can
reach a link router that does.
What stands between a link and an effect:

- **The app’s checks.** `GitHubLink` reads the string it passes, not Foundation’s
  decoded host: `https://`, a host of the reducer’s, no port but 443, no user or
  password, and at most `GitHubLink.maximumLength` bytes.
  The answer must name a canonical repository root, and the server starts on its
  `handoff`, which `metab` rebuilt from what its reducer kept, so a token or other text
  a sender put in the link never reaches the server’s arguments or its log.
  The dry run is given the link as sent, so the process table shows it, query included,
  for the dry run’s lifetime: about a third of a second, and at most
  `PresentDryRun.timeout`. The link itself is logged private.
  Every spawn is an argument array, never a shell, and alerts shorten what they show and
  leave out a link’s user name, password, query, and fragment.
- **`metab`’s checks.** Everything in the URL reducer: which pages open, the owner and
  repository grammar, credentials, ports, encoded delimiters, and dot segments, and the
  rule that an argument starting with a scheme is never a local path.
- **Bounds.** The queue’s, the questions’, and the runtime wait’s, and the question
  before a clone, which is the user’s consent to download a repository and read it with
  their sign-in.

A finding against this boundary is a security issue
([SECURITY.md](../../../SECURITY.md)).

### After a Crash

A crashed or force-quit app cannot stop its servers, so each server ends with the app.
The app starts it with `--exit-on-eof` and holds its stdin pipe, the kernel closes that
pipe however the app ends, and the server reads EOF and stops itself
(`src/metabrowser/cli/stdin_lifeline.py`); `LiveMetabTests` checks this against a real
server.
Nothing is recorded on disk to signal later, because between a check and `kill` a
pid can pass to another process.
Not covered: a server so wedged that its stdin watcher thread cannot run, which an
orderly quit still ends with SIGKILL, and descendants in other process groups.

## Choosing a metab

`RuntimeDiscovery.discover` runs on the first launch and from Settings > Find Again.
It tries, in order, the path a previous setup saved, `METABROWSER_METAB`,
`~/.local/bin/metab`, uv’s tool bin directory, the Homebrew prefixes, and last the login
shell’s `PATH`, which runs only when the earlier places miss `metab`, `git`, or `gh`,
because it runs the user’s shell startup files in the app’s name.
Setup saves the runtime with the paths of `git` and `gh` (`RuntimeSettings`), so a later
launch starts no process to find them.

Checking a candidate executes it, so the app runs a `metab` it found by itself only if
no other account can change it (`ExecutableTrust`): every directory and link from `/`,
and the file, belong to this user or root, none is writable by its group or every
account, and no access control entry grants a change.
A standard Homebrew prefix is group-writable, so its `metab` is refused.
The rule holds again just before each child spawns
(`RuntimeOperations.launchableSetup`). A file chosen with Choose metab… runs as chosen.

Every start asks for the accepted runtime twice (`FolderServer`): before it stops
anything, and just before the child spawns (`ServerSupervisor.mayLaunch`). While none is
accepted, a start spawns nothing, its windows say so, and it goes ahead once one is.
When searches, rechecks, and choices overlap, the one started last wins
(`RuntimeSelection`, `RuntimeOperations`).

The server’s environment is built from an allowlist, never inherited
(`ChildEnvironment`). `PATH` is the directories of the `git` and `gh` found at setup,
then the system’s, since a Finder launch would otherwise give the server Apple’s `git`
shim and no `gh`, and nothing from a Terminal launch’s `UV_*`, `VIRTUAL_ENV`, or
`PYTHONPATH` passes.

### The Version Floor

`MetabRequirement.minimumRelease` in `Sources/ShellCore/Setup/MetabVersion.swift` is the
oldest `metab` the app runs: the first release with `GET /api/identity`,
`--exit-on-eof`, `--present`, and `--recent` (`MetabRequirement.requiredFlags`). A
development build of that release counts as it, or no checkout would run, so the number
alone does not prove the flags, and `RuntimeDiscovery.validate` runs
`metab --exit-on-eof --present --recent --version`. A printed version decides by its
number; exit status 2 naming any of the flags means a build that predates it, which is
too old whatever its number; anything else rejects the `metab` with the probe’s last
line. Below the floor, discovery tries the next place.
`MetabRequirement.upgradeCommand` asks uv for a floor rather than a pin, because uv
keeps the requirement in the tool’s receipt.

The floor is always a minor release, `X.Y.0`: a `metab` change the app depends on ships
in a new minor or major release, never a patch
([Choosing a Version](../../publishing.md#choosing-a-version)). A checkout reports the
next minor release as its development version (`bump` in `pyproject.toml`), so a
checkout built after the change that raised the floor meets it.
`tests/test_macos_app_pins.py` holds both.

The app notices an upgrade by the executable’s fingerprint (`FileFingerprint`: device,
inode, size, modification time, and mode), compared every `SetupWatch.interval` and when
the app becomes active.
A change counts once two looks agree (`FileWatch`), and then nothing starts from the old
runtime until a check validates one.
If open folders run servers that the same `metab` started at another version, an alert
offers to restart them (`RuntimeUpgrade`). An upgrade run in Terminal can still reach
running servers’ environment before the app notices.

### First Run

When a search finds no usable `metab`, Settings shows only the missing steps, each a
command to copy (`SetupGuide`):

| Found | Steps shown |
| --- | --- |
| No uv | uv’s installer, then the `metab` step in a new Terminal window |
| uv, no `metab` | `RuntimeDiscovery.installCommand` |
| A `metab` in uv’s tool directory that does not run | A reinstall |
| A `metab` below the floor, or built before the flag | `MetabRequirement.upgradeCommand` |

Until the floor is on PyPI (`MetabRequirement.isReleased`), every case ends instead in
`make install` at the source checkout the app was built from, then Choose metab…. The
app asks a uv that passes `ExecutableTrust` where `metab` will appear
(`uv tool dir --bin`), watches there and every place discovery looks, and when `metab`
appears searches again and opens the folders that were waiting.
It never runs an installer itself.

A copy opened from its disk image, or translocated by Gatekeeper, cannot be replaced in
place. macOS has no API for either, so `LaunchLocation` reads the bundle’s path and
volume, as Sparkle does, and the app shows a notice that says to move it to
Applications.

## Windows

- **Title.** The folder’s short name, from `GET /api/identity` once the server is ready
  and from the path until then (`FolderIdentity.localFolder`). `window.title` is the
  short name too, or the full name while two open folders share a short name
  (`WindowTitle.windowTitles`). The page’s own `<title>` is for a browser’s tab.
- **Size.** `NewWindowFrame` sizes a new window as a share of its screen’s visible frame
  and cascades the next one from the window placed last.
- **Navigation.** `NavigationPolicy` keeps the server’s origin in the window.
  A clicked link to another `http`, `https`, or `mailto` URL opens in the default
  browser; the same URL reached by script, redirect, or history is cancelled, and so are
  `file://` and other schemes.
- **Downloads.** `WKDownload` with a save panel.
  A confirmed Replace downloads to a staging file on the same volume and renames it over
  the original only when it finishes (`StagedDownload`).
- **Crashes.** If the web content process dies, the window reloads within
  `RecoveryBudget.webContent`, and then shows the status view.
- **Reload.** Command-R reloads in every state a folder window can be in (`PageReload`,
  `PageMenu`): the page; its page again once the server answers a health check; or the
  server, as Retry does.
  A sheet the page opened is cancelled first (`PageSheets`).

### Tabs, Files, and Recents

- **Tabs.** Every folder window shares one tabbing identifier, so Merge All Windows and
  tab dragging combine any folders.
  `FolderPlacement` puts a new folder in a tab, a window, or as System Settings prefers.
- **Background tabs.** Each window’s shown tab keeps its page, and so do the most
  recently shown background tabs up to
  [`TabDiscardPolicy`](../../../apps/macos/Sources/ShellCore/Web/TabDiscardPolicy.swift)’s
  limit, whose comment holds its measurement.
  Every other background tab gives up its web view, which ends its WebContent process,
  and reloads from the running server when shown, keeping only its address.
- **Files.** A file opens in the most specific open folder that contains it, or else in
  its own folder, as `metab FILE` does (`OpenTarget`), at the view route `metab` spells
  (`PageAddress.view`). A page requested while the server is not ready loads once it is
  (`NextPage`). By design the open folder that takes a file never lies above the file’s
  repository root, and a file with no such folder opens its open root
  ([Open Modes](arch-open-modes.md#what-keys-on-the-root)).
- **Recents.** File > Open Recent lists `metab`’s
  [recent targets](arch-recent-targets.md#the-macos-app), which every server records as
  it starts, so the app decides nothing about the list and keeps none of its own.
  The Dock menu lists the same targets (`applicationDockMenu`), and a restored folder’s
  server, like any restart, is told not to record.

### Session Restore

`SessionStore` saves the folder windows, front first, with each window’s tabs, shown
tab, and frame and each tab’s folder and page, to `session.json` in
`AppIdentity.supportDirectory`, `FolderWindows.saveDelay` after a change and at quit
before the servers stop.
Each save renames a private temporary file over the old one, so a launch after a crash
finds a whole session, and two copies saving at once leave the last one’s.

A launch reads the file once, as a regular file of at most `SessionStore.byteLimit`, and
rebuilds at most
[`RestoreBudget.standard`](../../../apps/macos/Sources/ShellCore/Folders/SavedSession.swift),
whose comment holds its measurement.
Only each window’s shown tab loads its page.
Servers start one at a time, each after the one before is ready or has failed: the front
tab’s first, then the tabs the other windows show, then the rest (`RestoreQueue`,
`RestoreRun`). A tab selected meanwhile starts next.

The file may have been edited, and a folder on a path replaced or relinked, so every
root is admitted again before anything starts (`RootAdmission`). Only a root whose
identity is certain warms in the background: a walk from `/` opens each component with
`O_NOFOLLOW`, enters no mount but the system’s and the Data volume’s, and never opens a
protected location (`ProtectedLocations`); the folder it reaches must be on the home
folder’s volume, and the kernel’s name for it is the root’s identity.
Anything less certain waits for its tab under its saved spelling, and selecting the tab
resolves the path then (`RootActivation`), moving its tabs to the folder it now leads
to. A folder in a protected location starts only when one of its tabs is selected, so a
launch raises no privacy prompt for a folder nobody is looking at.
A background root is admitted again at its turn and just before its server spawns; a
process that changes the path after that check can still win, and macOS enforces its
privacy grants regardless.

## The Title-Bar Accessory

AppKit draws a system title in one font and color, so the window hides it and draws its
own in a leading title-bar accessory (`TitleAccessoryController`), and the app icon’s
mark in a trailing one (`TitleBarMarkController`).

- **Placement.** On macOS 26 a leading accessory sits where the system title sits, after
  the window buttons, in the same font and title-bar height; `TitleAccessory.swift`
  holds the measured insets.
  A centered toolbar item would make the title bar taller and center the title, which
  macOS 26 puts at the leading edge.
- **No proxy icon.** AppKit drops the proxy icon when a leading accessory is present, so
  Command-click, right-click, or VoiceOver’s Show Menu on a local folder’s title opens
  its path menu, from `representedURL`.
- **The mark.** The partial M and the B, drawn as paths from the icon masters’ glyph
  group, which `AppIcon/make-glyphs.swift` copies into `AppIconMarkGeometry.swift`; a
  test checks the copy against both masters.
  `TitleBarMarkLayout` places it, and `AppIconMark.titleBarFills` gives the light title
  bar deeper tints that meet WCAG contrast for graphics; both comments hold their
  measurements.
- **A link.** A click opens `ProjectLinks.repository` in the default browser, and a
  press that moves `TitleBarMarkInteraction.dragDistance` drags the window instead.
  `TitleBarMarkInteraction` decides each pointer event and is tested event by event.
- **System behavior.** The title dims when its window is not main in the active app,
  AppKit dims the mark with it, and both follow light and dark mode.

## WebKit Differences

The page is the one any browser opens, and the app handles what WebKit does differently:

- **`window.print()`** reaches only private `WKUIDelegate` methods, so a user script
  replaces it in the main frame with a message to the app (`PagePrintRequests`), which
  prints only for a document whose security origin is the server’s own.
  It checks the origin, not the URL, because a `/raw` response’s CSP sandbox gives it an
  opaque origin.
- **A dropped file** would make WebKit navigate to its `file://` URL, so
  `DropAwareWebView` takes file and folder drops before WebKit sees them and hands them
  to the app (`FileDrop`).
- **`javaScriptCanOpenWindowsAutomatically`** defaults to on in macOS, so
  `WebConfiguration.restrict` turns it off and a previewed HTML file cannot open tabs by
  itself.
- **Printing** runs modally for the window, which `BrowserWindowController.printPage`
  explains.

### Measured in WebKit

The [packaging brief](../research/research-2026-11-08-macos-app-packaging.md) keeps the
`WKWebView` shell only if WebKit holds the large-content bounds that
[rendering large content](../../large-content-rendering.md) sets in Chrome, within 1.3
times Chrome in every back-to-back pair on one machine.
`make macos-webkit-gate` measures that.
Its run of 2026-11-11 failed: layout is where WebKit falls behind, most in the source
and binary views.
[QA: WebKit Measurement Gate](../qa/qa-2026-11-11-webkit-measurement-gate.md) records
the method, every figure, and the print and drop checks.

## Why It Lives in This Repository

The host protocol is a contract between the app and `metab`, so a change to it lands in
both in one commit, as [AGENTS.md](../../../AGENTS.md#compatibility-and-legacy-code)
asks of internal contracts.
Nothing in `apps/` ships to PyPI: `devtools/check_distribution.py` fails the build if an
`apps` path reaches the sdist or wheel.
A separate repository would make sense if the app gained its own release cadence, needed
signing secrets this repository’s CI should not hold, or had to support several `metab`
versions through a published protocol.

## Planned

Host mode (port 0, a ready line, a session token, `/healthz`, and a shutdown that ends
every descendant), a rootless runtime report with explicit tool paths and an app-managed
runtime, Settings served by Metabrowser, a Developer ID release built by CI, updates,
and attaching to an agent’s server are planned in the
[native macOS app plan](../specs/active/plan-2026-11-10-native-macos-app.md), with the
reasons in the
[packaging brief](../research/research-2026-11-08-macos-app-packaging.md)’s Layering
section and Recommendations.
[Open Modes](arch-open-modes.md#the-file-menu) designs the File menu’s Open Folder…,
Open URL…, and Open Recent, and what each opens; Open URL…’s offer of a known checkout
is `mb-bkk2`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
