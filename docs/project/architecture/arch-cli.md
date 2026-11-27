# Architecture: Command Line

**Status:** Built, in `src/metabrowser/cli/`, including `--present`: a handoff to the
macOS app that the app does not yet answer, or a browser on a detached `metab` server,
as the `open_in` preference chooses.
Planned: a reply from the app, navigation of a page already open, and reuse of a running
server ([native macOS app plan](../specs/active/plan-2026-11-10-native-macos-app.md),
Phase 3;
[open-anything plan](../specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md)).

`metab` is one flat command whose default operation is serving a folder.
Every other operation is a mode flag on the same command.
The CLI owns argument parsing, mode dispatch, the serving process’s lifecycle, and how
that process ends; the application it serves is described in
[Server and Content](arch-server-and-content.md).
Every option and its meaning for users is in [Command Line](../../command-line.md).

## Modes

`_resolve_mode` in `cli/main.py` picks exactly one mode per invocation and rejects two
mode flags together.
`_MODE_OPTIONS` lists the options each mode accepts.
An option the user typed that the mode does not accept is a usage error; Click’s
parameter-source tracking tells a typed option from a default, so defaults never trigger
a rejection. `_MODE_FORMATS` does the same for `--format`, so a format a mode cannot
produce is refused rather than ignored.

| Mode | Selected by | Module |
| --- | --- | --- |
| Serve a folder | No mode flag | `serve.py` |
| Serve a Git source | No mode flag, with a `file://` or `https://` ROOT | `git_pin_cli.py` |
| Acquire only | `--no-serve` | `acquire_cli.py` |
| Issue one route | `--api ROUTE` | `api_cli.py`; `acquire_cli.py` for cache routes; `git_pin_cli.py` on a pin |
| Report one selection | `--show PATH` | `show_cli.py`; `git_pin_cli.py` on a pin |
| Navigation check | `--check-api` | `check_api.py` |
| Inventory walk | `--walk` | `walk_cli.py`, with `walk.py`, which calls the Python walker directly rather than the provider |
| Change set | `--diff SPEC` | `diff_cli.py` |
| Remote host | `--remote HOST` | `remote.py` |
| Plugins and the setup | `--plugins`, `--plugin NAME`, `--doctor` | `plugins.py`, with `doctor.py` for the setup checks |
| Open a target in the macOS app or a browser | `--present` | `present.py`, with `open_in.py` for the preference |
| Recent targets | `--recent`, `--recent-add`, `--recent-forget`, `--recent-clear` | `recent_cli.py`, over [`recent_targets.py`](arch-recent-targets.md) |

`_classified_root` decides whether ROOT is a local path or a Git source.
First, `_root_in_full` writes `https://` before an argument that names nothing on disk
and begins with a host a provider’s reducer claims, such as `github.com/owner/repo`;
`--present` does the same before it reads ROOT. An `ssh` source is refused in every
mode. A mode that serves, shows, or checks a Git source runs under the forced untrusted
profile described in
[Server and Content](arch-server-and-content.md#acquired-git-sources).
The diff, API, acquire, and show modes import their modules inside their branch, so a
mode on a local folder does not load the Git revision machinery it never uses.

`--event-log` is no mode but a way to name ROOT, for every mode that takes a local
folder (serve, `--api`, `--show`, `--walk`, and `--check-api`): `_metab` replaces ROOT
with the directory the event log lives in (`cli/event_log_cli.py`, over
`event_log.log_directory`), refuses a ROOT beside it, and, when serving without
`--path`, selects the newest segment, so `metab --event-log` opens the log in the
event-log plugin ([Real-Time Debugging](../../realtime-debugging.md#browsing-the-log)).
A server whose folder is the log’s directory opens no log of its own
(`event_log.open_log`’s `served_directory`), so browsing it does not write to it, and
says why; a server whose folder only holds the directory logs, and skips the requests
for what is inside it (`event_log.quiet_request`).

`--present` is a client mode, and reads ROOT without `_classified_root`, because a
target it cannot present is a refusal it reports as data, with
`PRESENT_REFUSED_EXIT_CODE`, rather than an `Error:` line;
[Presenting to the App](#presenting-to-the-app) describes it.

`cli/entrypoint.py` is the console-script boundary.
It imports `cli/main.py` inside a `try`, so a Ctrl-C while Python is still importing
exits with `INTERRUPTED_EXIT_CODE` (`cli/exit_codes.py`) and no traceback.
`cli/main.py`’s `_run_cli` prints a `CLIError` as `Error: …` and exits with status 1,
and silences a closed stdout or stderr so a pipe to `head` does not turn success into a
flush error at exit.

## The Serve Lifecycle

`run_serve` in `cli/serve.py` serves a folder in this order:

1. **Interrupt handler first.** `_stop_now` is installed for `SIGINT` before anything
   starts a thread or a watcher, so no window exists in which serving has begun and a
   Ctrl-C has nowhere to land.
2. **Configuration.** The dotenv chain loads, then `apply_capabilities` resolves the
   trust profile, then the log level applies.
   The log level must precede the server import, because `server.py` configures logging
   when it is imported.
3. **Root.** A file given as ROOT becomes its parent folder plus a `--path` selection.
4. **Plugins, then the selection.** `apply_extra_plugin_dirs` merges `--plugins-dir`
   with `METABROWSER_PLUGINS_DIRS`, and then `validate_contained_path` checks that a
   selection stays inside the root.
5. **Server import.** `serve_until_interrupted` imports `server.py`, which discovers
   plugins at import. It then resolves KPress’s browser assets and the static asset
   stamps, so the first page request does not pay for them while the inventory walk
   competes for the CPU.
6. **Port and root.** `listen_on_available_local_port` walks `port_search_range` upward
   from `--port` and returns a listening socket on the first free port, which Uvicorn
   later serves on. The server holds its port from here, so the banner never names a port
   another server can take while startup finishes.
   The socket’s family is the host’s, so an IPv6 `--host` is served, and `::` listens
   for both families. The root attaches, and a concrete `--host` joins the Host
   allowlist, an IPv6 literal in the brackets a `Host` header carries.
7. **Banner and browser.** The banner prints the canonical `/view/` URL, never the bare
   origin, which only redirects.
   `url_host` (`server_utils.py`) chooses its host: loopback for a wildcard bind, and an
   IPv6 literal in brackets.
   A daemon thread runs `wait_for_http_ok_then` (`cli/http_readiness.py`), which polls
   that URL and opens the browser only after it returns an HTTP success; an accepted TCP
   connection or the origin’s redirect is not readiness.
8. **Serving.** Uvicorn runs with no graceful-shutdown wait, since open event streams
   would otherwise hold a shutdown forever.
   Uvicorn binds once the application lifespan (`_lifespan` in `server.py`) has started:
   it attaches the served subject, opens the inventory, and starts a served mirror’s
   refresh jobs. Opening the inventory does not wait for discovery, which runs as a
   background task, so the first page is answered while the walk runs.
9. **Startup failure.** Uvicorn returns normally when the lifespan fails, so
   `serve_until_interrupted` checks `started` and raises the subject’s open failure as a
   `CLIError`.

`run_serve_pin` serves a Git source the same way, with two differences.
It acquires the source first, under `run_cancelling_on_hangup`, and installs the serving
interrupt handlers with `stop_on_interrupt` only after acquisition ends.
And it hands the server an opener rather than a folder: the lifespan opens the pin in
the serving event loop and closes it at shutdown.

## In-Process `--api` Dispatch

The data modes read the same server the browser reads without binding a port.
`InProcessClient` (`cli/asgi_client.py`) runs one ASGI lifespan, then issues each
request as a complete ASGI HTTP exchange through the real middleware stack, routing, and
serialization. That is what lets a transcript prove the wire, its parameters, envelope
keys, and status codes, rather than only the library beneath a route; the parity rule in
[AGENTS.md](../../../AGENTS.md) depends on it.

- **Headers.** A request carries `Host: testserver`, which the Host allowlist admits,
  and no `Origin` or `Sec-Fetch-Site`, which the same-origin check admits as a
  non-browser caller.
- **Bounds.** `LIFESPAN_TIMEOUT_S` bounds startup and shutdown and `REQUEST_TIMEOUT_S`
  bounds each request.
  An event-stream route has no terminating response, so the client refuses it as soon as
  its headers arrive.
- **Waiting for the index.** Routes in `_INDEX_DEPENDENT` (`cli/api_cli.py`) change once
  the scan finishes, so `--api` polls `/api/index/progress` until the index is done,
  truncated, or failed, bounded by `--index-timeout`. Other routes skip the wait.
  The transcript records the index state the answer was produced under.
- **Bodies.** `--data` sends a POST body from a file or from standard input (`-`),
  bounded by `MAX_REQUEST_BODY_BYTES` in `server.py`, the largest body a route reads.
- **Background work.** Leaving the client shuts the application down, which cancels
  background work. Before leaving, `--api` drains the jobs its own request started and
  every job those start in turn, such as the status scan a list’s look at the mirror
  starts, under one deadline for all of them (`_REFRESH_DRAIN_S`,
  `RefreshCoordinator.drain`), and follows a `202` answer to the status route it names.
- **Output.** With no `--format`, the output is the transcript every golden pins: the
  route, the status, and the envelope.
  An explicit format prints the document alone, for a tool to parse.
  The exit status is nonzero unless the route succeeded.

`--show` and `--check-api` use the same client.
On a Git source, `git_pin_cli.py` attaches a `GitRevisionSubject` and drives the same
stack; a cache route (`/api/cache/…`) instead runs against an empty throwaway root after
acquisition, so cache inspection cannot expose origin objects through `/api/tree`.

## Presenting to the App

`run_present` in `cli/present.py` resolves ROOT, decides where it goes, and, unless
`--dry-run`, hands it to the macOS app or starts a server for a browser.
A dry run loads nothing beyond what `metab --version` loads except `cli/present.py`, the
preference’s reader of `config.yml` and the owner-only file helpers under it, the
property-list reader, and for a link the URL grammar, and starts no process and opens no
connection, which `test_present_dry_run_loads_little_beyond_version` in
`tests/test_plugin_public_api.py` holds, so the app can run `--present --dry-run` to
check what a user types.
It still pays `metab`’s startup, which `--version` measures, because `cli/main.py`
imports the serve mode’s modules before a mode is chosen.

1. **Resolve.** `resolve_target` reads a local ROOT as serve mode does: the resolved
   folder, or a file’s folder with the file selected, and `--path` within it.
   Anything else goes through `classify_root_argument` with `url_reducers()`, which
   imports each provider’s reducer without the provider.
   A source is presentable only when a reducer claims it and can spell it back as a web
   URL (`ProviderUrlReducer.web_url`), which only GitHub’s does; that URL, canonical and
   ASCII, is what the app is handed, and its root is the repository URL with no ref.
   Its `page` is what `selection_view_href` (`cli/selection_href.py`) gives a pinned
   server where the URL leaves one reading, and `None` where only the mirror knows where
   a ref ends or what an abbreviated commit ID names, or only the cache which changed
   file a Changes tab URL’s `#diff-<hash>` anchor names (`_source_page`). A file named
   alone is handed over alone, for the app to place as it places any file; a file
   `--path` names is handed over after ROOT, which makes the app open the root named.
2. **Decide.** `resolve_open_in` (`open_in.py`) reads the preference from `--open-in`,
   `METABROWSER_OPEN_IN`, then `open_in` in `config.yml`, which it reads alone, through
   the owner-only helper and within `CONFIG_MAX_BYTES` (`config_file.py`), without the
   record’s contract and its schema library; `tests/test_open_in.py` holds it to
   `read_config`. `decide` sends `browser` to a browser without a lookup; otherwise it
   finds the app as below, and under `auto` sends a target no app takes, any code
   `DELIVERY_EXIT_CODES` maps to `PRESENT_NO_APP_EXIT_CODE`, to a browser, and one
   LaunchServices could not be asked about nowhere.
   A dry run prints the decision.
3. **Find the app.** `bundle_lookup` asks LaunchServices through
   `LSCopyApplicationURLsForBundleIdentifier` for each identifier in turn, release
   first, and takes the bundle LaunchServices prefers, the one `open -b` opens.
   That is the database `open -b` reads; Spotlight’s index (`mdfind`) is not asked,
   because it can be off or leave out the folder an app is in.
   Off macOS the lookup is `None` and nothing is sent.
   A lookup LaunchServices does not answer, as under a sandbox that denies its database,
   raises `AppLookupError` rather than reading as no app.
4. **Check what the app takes.** A folder inside the root is refused before the lookup,
   because the app opens each folder in a window of its own.
   Every identifier’s bundle passes `app_refusal` or the next identifier is tried, so a
   stray registration of one does not hide an installed build of the other: the bundle
   is at one of `install_locations()` (unless `ANY_APP_LOCATION_ENV` is `1`), with `~`
   read from the password database rather than `$HOME`, compared with its folder’s links
   resolved and in one Unicode form, and not itself a link, because LaunchServices
   registers a bundle wherever it was opened; its `Info.plist`, read as a bounded
   regular file, names it `APP_BUNDLE_NAME`; and it sets `OPENS_URLS_KEY` true, because
   an older app drops a URL while `open` still succeeds and an app an override names
   must not be handed a file it would run.
   It is a path check, not a signature; a release’s team identifier is not checked.
5. **Send.** `/usr/bin/open -b <bundle id> <handoff>`, by its absolute path
   (`open_executable`), bounded by `OPEN_TIMEOUT_S`. Exit 0 from `open` means
   LaunchServices took it, so the report says `confirmed: false` until the app can
   reply.
6. **Serve for a browser.** `serve_detached` starts `server_command`, this interpreter
   running `metab ROOT` with its `--path` and without `--no-open`, through
   `subprocess.Popen` with `start_new_session`, stdin at `/dev/null`, stdout and stderr
   in a `mkstemp` log in the temporary folder, and every other descriptor closed, so the
   server outlives the command and its terminal and nothing reading the command’s output
   waits on it. It reads the log for the `Serving <root> at <url>` line, which
   `serving_url` parses as the macOS app’s `CLIServeLaunch` does, then asks that address
   for `GET /api/identity` until it answers as a server of the target’s root
   (`_is_target_identity`), the server exits, or `server_announce_timeout_s` passes.
   Serve mode prints the line after it finds a free port and before uvicorn binds it, so
   two servers started together can print one address; the identity tells servers of
   different roots apart, and binding before printing (`mb-afxa`) would close the race
   for every reader of the line.
   Before it starts anything, `allow_browser` reads `present_browser` from `config.yml`
   (`open_in.py` `browser_delivery_allowed`), and turns a decision for a browser into
   `browser_off` when it is false.
   No option of the command overrides it, and `cli/main.py` refuses `--config-dir` with
   `--present`; the configuration directory is the environment’s
   (`METABROWSER_CONFIG_DIR`, `XDG_CONFIG_HOME`, `HOME`), and one without `config.yml`
   allows a browser. The server opens the browser itself once its page answers, as serve
   mode always does. Nothing records the server: the report’s `pid` is how to stop it.
   Tests start no real server unless they say so: an autouse fixture in
   `tests/conftest.py` points `server_command` at a program that exits 1.
7. **Report.** A `key: value` report, or with `--format json` one object with the
   preference, the handoff, the bundle’s path or the server’s `url`, `pid`, and `log`,
   and a `code`; a refusal exits with `PRESENT_REFUSED_EXIT_CODE`, and each delivery
   code with its status in `DELIVERY_EXIT_CODES` (`cli/exit_codes.py` documents the
   statuses). `doctor_open_in` gives `metab --doctor` the preference, its source, and the
   app a lookup finds, with the oldest `metab` that app declares it runs
   (`MINIMUM_METAB_KEY`), sending nothing.

## Remote Tunnels

`run_remote` (`cli/remote.py`) serves a directory on another machine through SSH:

1. A free local port is found by walking upward from `--base-port`.
2. One SSH command runs `remote_port_probe_script` on the host, which walks upward from
   the same base, so several sessions to one host coexist and the tunnel cannot land on
   another session’s server.
3. A second SSH command forwards the local port to the remote one and runs
   `metab PATH --port P --host 127.0.0.1 --no-open` on the host.
   With `--gcp`, both commands use `gcloud compute ssh` with `--zone` and `--project`
   (or `METABROWSER_GCP_PROJECT`); otherwise `ssh` with `--ssh-options`.
4. `wrap_with_stdin_watchdog` (`cli/ssh_utils.py`) wraps the remote command so the
   remote server dies when the SSH channel closes.
   Non-TTY SSH does not reliably deliver `SIGHUP` to remote processes, so the wrapper
   runs the server in the background, reads the channel with `cat`, and kills the server
   at end of input.
5. `SIGINT` and `SIGTERM` are forwarded to the SSH process.
   The browser opens after the tunneled `/view/` URL answers, as in local serving.

The remote host needs the same Metabrowser version, because the tunneled command uses
the flat CLI syntax.
Exit status 127 from SSH means `metab` is not on the remote `PATH`, and the command says
so.

## Process Exit

### Interrupts

One Ctrl-C stops a server at once.
This is a local, single-user, read-only browser: no request in flight is worth a
reader’s wait, and nothing buffered needs a graceful flush.
`_stop_now` writes `Stopping Metabrowser.` to stderr with a raw nonblocking write
(`write_notice_now_or_never` in `cli/common.py`), which takes no lock the interrupted
thread may hold and is skipped if stderr cannot take it now.
It then calls `stop_process_groups` and ends the process with `exit_after_notices`,
which restores each stream’s blocking mode and calls `os._exit`. The status is
`INTERRUPTED_EXIT_CODE`, or `HANGUP_EXIT_STATUS` (`cli/hangup.py`) for a hangup.

`_run_until_interrupted` keeps that handler installed for the whole run.
Before Uvicorn captures signals it is ours; while Uvicorn serves, its `handle_exit`
calls `_stop_now`; after Uvicorn returns, it restores ours and re-raises what it
captured, which lands on `_stop_now` again.
A handler rather than `SIG_IGN` covers the first and last windows: `SIG_IGN` discards a
signal rather than deferring it.

Acquisition Git and `gh` run as leaders of their own process groups, so a timeout or a
cancellation can kill the helpers they fork.
That takes them out of the terminal’s foreground group, so a hangup or `kill <pid>`
reaches only `metab`. During acquisition, `run_cancelling_on_hangup` treats `SIGHUP` and
`SIGTERM` as Ctrl-C: it cancels the main task, whose cancellation kills Git’s group, and
exits with 128 plus the signal number.
While serving a Git source, `stop_on_interrupt` routes `SIGHUP` to `_stop_now`, and
`SIGTERM` remains Uvicorn’s graceful shutdown, whose lifespan cancels the refresh and so
kills its Git. A signal ignored on entry, as under `nohup`, stays ignored.

### Stopping When Stdin Closes

`--exit-on-eof` (`cli/stdin_lifeline.py`) stops the server when its stdin reaches end of
input. It is for a parent that starts `metab` and holds its stdin open, as the macOS app
does: however the parent ends, by quitting or by crashing, the kernel closes the pipe,
and the server stops itself.
Nothing has to find it later by process ID, a number the kernel may by then have given
to another process.

- **Opt in.** Without the flag stdin is ignored, so a server started with stdin at
  `/dev/null` serves as usual.
  With it, a stdin that is not open at all is refused before serving.
  Whatever arrives on stdin before end of input is read and dropped, and a read error
  counts as the end.
- **When the watch starts.** `cli/main.py` starts the watch as soon as serve mode has
  its command line, before reading ROOT, dotenv files, the server’s and plugins’
  imports, KPress’s assets, a Git source’s acquisition, or the port search.
  A server held up by a slow disk or a fetch still stops when its stdin closes.
  The watch and startup run side by side, so a stdin closed from the start can stop the
  server before it prints its address.
  Python’s start, the CLI’s own imports, and argument parsing come first: a stdin that
  closes during them is seen as soon as they end, and a hang there is not covered.
  A stdin that closes while startup is failing ends the process either way, with the
  failure’s status or with `STDIN_CLOSED_EXIT_STATUS`.
- **The stop.** `stop_for_closed_stdin` runs on the watcher thread and stops as one
  Ctrl-C does: it writes `STDIN_CLOSED_NOTICE` to stderr if stderr can take it now,
  kills the process groups, and exits at once with `STDIN_CLOSED_EXIT_STATUS`. It does
  not wait on the server’s event loop, even a stuck one.

### Killing Process Groups

`stop_process_groups` (`git/process.py`) refuses new process groups from then on and
kills every group this process leads, each with every helper in it.
A fetch holds its store’s lock, and a group would outlive the server, so each must go.

- **Finding them.** The stop reads the kernel’s list of this process’s children, so it
  also kills a group whose spawn has not returned.
  A look costs a few system calls per child; on a Linux kernel without per-thread child
  lists it reads every process’s `/proc` entry.
- **Waiting.** It waits only for a spawn under way on another thread, at most
  `SPAWN_WAIT_S`, then looks at the children once more.
- **What escapes.** A child that has not begun running Git when that wait ends; with
  Ctrl-C or a hangup, a child the interrupted thread had forked that had not yet begun
  running Git, since that thread gets no wait; and the helpers of a Git whose start
  failed, which asyncio kills alone.
  On systems other than macOS and Linux, which cannot list a process’s children this
  way, a spawn under way is not covered.
- **Reuse of process IDs.** Each child is confirmed to be this process’s own and not yet
  reaped just before it is signalled.
  `_unreaped_child` records why the remaining window, in which another thread could reap
  it and the system reuse its ID for a new group leader, is negligible.

Git that only reads runs in the server’s own process group and is not signalled; it
holds no lock, and it ends when it next writes to, or reads from, the server that is
gone.

## References

- [Command Line](../../command-line.md): every mode and option
- [Server and Content](arch-server-and-content.md): the application the serve mode runs
- [Views, Models, and Routes](arch-views-models-routes.md): the routes `--api` reaches
- [Development](../../development.md): the parity rule’s rationale

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
