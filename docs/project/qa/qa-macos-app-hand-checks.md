# macOS App Hand Checks

These checks cover what the app’s unit tests cannot reach: what AppKit, WebKit, and
macOS do with the decisions `ShellCore` makes, which is the platform behavior the
[packaging brief](../research/research-2026-11-08-macos-app-packaging.md) exempts from
the parity rule. Run them against a built development app after a change to the behavior
they check. [The app’s README](../../../apps/macos/README.md) says how to build it, and
[its architecture](../architecture/arch-macos-app.md) explains what each check
exercises.

Quit any other copy of Metabrowser first, a release included: another development build
has the same bundle identifier, and every copy writes the same logs folder and saved
session.

## Servers and the Runtime

```shell
app="$PWD/apps/macos/build/dev/Metabrowser.app"
logs="$HOME/Library/Logs/Metabrowser"
folder="$(mktemp -d)"
```

1. **Which build.** `open -a "$app" "$folder"`, then Metabrowser > About Metabrowser.
   Below the version is “Development build · VERSION (BUILD) · COMMIT”, the commit with
   `-dirty` for uncommitted changes.
   The Dock shows the canary icon, and Help > Reveal Logs Folder opens `$logs`.
2. **Health check.** With the folder open, find its server (`pgrep -f -- "--no-open"`)
   and stop it without ending it: `kill -STOP PID`. Bring the folder back (Command-click
   a link in it, or open the folder again).
   Within `SupervisorPolicy.healthDeadline` and then `shutdownGrace` (a stopped process
   holds SIGTERM until SIGKILL ends it), the window says “The server stopped answering”
   and offers Retry, and Retry serves the folder again.
   Done with a Command-click, the new tab shows the clicked page after Retry, not the
   folder’s first page.
   With the server answering,
   `printf 'a\n' > "$folder/a.md"; printf 'b\n' > "$folder/b.md"` and
   `open -a "$app" "$folder/a.md" "$folder/b.md"` end on `b.md`.
3. **stdout and stderr in the log.** `tail "$logs"/*.log` shows the server’s `Serving`
   and `Plugins:` lines, which came through stdout.
   A server serving without trouble writes nothing to stderr.
   What it writes there when its stdin closes, “Stopping Metabrowser: stdin closed.”,
   ends the folder’s log after the crash in step 4.
4. **After a crash.** With the folder open,
   `pkill -9 -f "$app/Contents/MacOS/Metabrowser"`. Within a second
   `pgrep -fl -- "--exit-on-eof"` finds no server, and the folder’s log ends with
   “Stopping Metabrowser: stdin closed.”
5. **An orderly quit.** Metabrowser > Quit Metabrowser leaves no server.
6. **A `metab` the app does not run.** Quit, forget the saved runtime
   (`defaults delete io.github.jlevy.metabrowser.dev`),
   `printf '#!/bin/sh\necho metab 9.9.9\n' > /tmp/metab; chmod +x /tmp/metab`, and
   `open --env METABROWSER_METAB=/tmp/metab -a "$app"`. Settings > Places looked lists
   `/tmp/metab` as not run because `/private/tmp` can be changed by every account, the
   log says “not running /tmp/metab”, and the runtime is not 9.9.9. Choose metab… and
   `/tmp/metab` then uses it, saying it runs because you chose it.
   `rm /tmp/metab` and forget the saved runtime again afterward.

## Files, Tabs, Recents, and Restore

Set `APP` to the development build and make some folders:

```shell
APP="$PWD/apps/macos/build/dev/Metabrowser.app"
LOGS="$HOME/Library/Logs/Metabrowser"
mkdir -p /tmp/mb-check/{a/sub,b,c,d,e,f,g} "$HOME/Documents/mb-check"
echo '# notes' > /tmp/mb-check/a/notes.md; echo '# deep' > /tmp/mb-check/a/sub/deep.md
log stream --predicate 'subsystem == "io.github.jlevy.metabrowser.dev"' &  # the app log
```

1. **A file.** `open -a "$APP" /tmp/mb-check/a/notes.md` opens a window for `a` showing
   `notes.md`. `open -a "$APP" /tmp/mb-check/a/sub/deep.md` shows `deep.md` in that same
   window, and `pgrep -fl 'metab /private/tmp/mb-check'` still lists one server.
   `open -a "$APP" /dev/null` shows an alert.
   File > Open… chooses a file too.
2. **Recents.** After opening `b`, File > Open Recent and the Dock icon’s menu list `b`
   above `a`, and `metab --recent`, run with the `metab` the app uses, lists the same
   two. After `metab /tmp/mb-check/c --no-open` in Terminal, stopped with Control-C, and
   a switch back to the app, File > Open Recent lists `c` first.
   Opening `a` again, while its window is open, moves it to the top.
   **One list in the Dock:** drop `f` on the Dock icon, run
   `open -a "$APP" /tmp/mb-check/g`, which opens it as Finder’s Open With does, and
   choose `b` with File > Open…. The Dock icon’s menu then lists each folder exactly
   once, in the order File > Open Recent shows, with nothing but separators between that
   list and the app’s own items, and choosing `g` in it brings `g`’s window forward.
   A folder listed twice, or a second group of folders, is macOS’s own recent-documents
   list beside the app’s, and fails the check: the app clears macOS’s list only once, at
   launch, and would have to clear it after each open.
   Close the windows of `f` and `g`, and look at the Dock menu again after the quit and
   relaunch below. After `rm -r /tmp/mb-check/c`, choosing `c` shows the alert and
   removes it. Clear Menu empties both menus and `metab --recent`. After a quit and a
   relaunch that restores `a` and `b`, both menus and `metab --recent` list them in the
   order they had before the quit.
   `defaults read io.github.jlevy.metabrowser.dev` shows no `recentFolders` key.
3. **Tabs.** With Settings > Open folders in set to Tabs, opening `c` and `d` adds them
   as tabs of the front window; set to Windows, opening `e` gives it a window, and
   Window > Merge All Windows then merges every folder into one window.
   With the setting on System Settings and Desktop & Dock > “Prefer tabs when opening
   documents” at Always, a new folder opens as a tab.
4. **Discarded pages.** With `a` to `e` as tabs of one window, select each in turn: once
   more tabs are in the background than `TabDiscardPolicy.defaultLiveBackgroundTabs`,
   the app log says “discarding the page of background tab” for the tab shown longest
   ago, and `ps -axo pid,command | grep -c '[W]ebContent'` drops by one.
   Selecting that tab reloads its page, with no “Starting” text, at the top of the page
   and with no Back or Forward history, since a discarded tab keeps only its address.
5. **Restore.** Make one window with tabs `a` and `b`, `b` selected, and a second window
   with `c`, and quit. `session.json` in `~/Library/Application Support/Metabrowser/` now
   lists them; the next launch logs “restoring 2 window(s): 3 server(s) to start”, the
   windows and tabs come back, and `grep -h 'started pid' "$LOGS"/{a,b,c}-*.log` with
   its timestamps shows `b` started first, then `c`, then `a`, each after the one before
   it was ready.
6. **Protected locations.** Add `~/Documents/mb-check` as a background tab, quit, and
   launch again: that tab says Metabrowser opens it when you select it, and
   `pgrep -fl 'Documents/mb-check'` finds no server until you select the tab.
   Once Documents access is granted, no prompt appears either way.
   To see that the restore raises none, the person at the Mac first resets that grant
   (`tccutil reset SystemPolicyDocumentsFolder io.github.jlevy.metabrowser.dev`) and
   then checks that the prompt waits for the tab’s selection: the waiting tab still
   shows the folder’s name and icon, and whether reading those can prompt is untested.
7. **A folder replaced by a link.** With `d` as a background tab of `a`’s window and `e`
   not open, quit, then
   `mv /tmp/mb-check/d /tmp/mb-check/d-old; ln -s /tmp/mb-check/e /tmp/mb-check/d`, and
   launch: `d`’s tab says Metabrowser opens it when you select it.
   Select it: the app log says it “now leads to /private/tmp/mb-check/e”, the tab shows
   `e`, and `open -a "$APP" /tmp/mb-check/e` and `open -a "$APP" /tmp/mb-check/d` bring
   that tab forward, while `pgrep -fl 'metab /private/tmp/mb-check/[de]'` lists one
   server, for `e`. Put `d` back with
   `rm /tmp/mb-check/d; mv /tmp/mb-check/d-old /tmp/mb-check/d`.
8. **Off, and empty.** With Settings > “Reopen the last session’s folders when
   Metabrowser opens” off, a launch restores nothing.
   With it on, closing every window before quitting restores nothing.
   After each quit, `pgrep -fl 'metab /private/tmp/mb-check'` finds nothing.
9. **A dropped file.** Drag `/tmp/mb-check/a/notes.md` from Finder onto the window of
   `a`: it shows `notes.md`. Dragged onto another folder’s window, it opens `a` (or
   shows the file in `a`, if open).
   A drag of text or a web link is still the page’s.
10. **A root above the folder picked.** This check applies once a path opens at its
    repository’s root, which is designed in
    [Open Modes](../architecture/arch-open-modes.md#resolving-a-target-to-a-root) and
    not built. Make `~/Documents/mb-check` a repository holding `sub/notes.md`
    (`git init`, `git add`, and one commit), reset the Documents grant as in step 6, and
    choose `sub` with File > Open…. Note which folder the window names, how many prompts
    appear and for which folder, and that the tree lists the repository’s root once
    access is granted. Repeat with the repository in `~/Desktop` and in `~/Downloads`.
    How macOS treats a served root above the folder chosen in the open panel is
    untested.

## GitHub Links

With the development build running a `metab` from this checkout, and `gh` signed in:

```shell
APP="$PWD/apps/macos/build/dev/Metabrowser.app"
APP_ID=io.github.jlevy.metabrowser.dev
REPO=https://github.com/jlevy/metabrowser
# The repository's log: its name, then 8 hex digits of its URL's SHA-256 (ServerLog).
LOG="$HOME/Library/Logs/Metabrowser/metabrowser-$(printf %s "$REPO" | shasum -a 256 | cut -c1-8).log"
```

1. **A pull request.** `open -b "$APP_ID" "$REPO/pull/517"` opens a window at the pull
   request’s page, titled for the repository until the server answers and then as
   `metab` names the pull request.
   If the cache did not hold the repository, a confirmation named
   `github.com/jlevy/metabrowser` came first.
   `pgrep -fl -- "metab $REPO/pull/517"` lists one server, on a port from
   `CLIServeLaunch.repositoryBasePort` up, and `"$LOG"` holds its clone or cache line.
2. **Another revision of an open repository.** `open -b "$APP_ID" "$REPO/tree/main"`
   brings that window forward, which says it is starting and then shows `main`’s tree,
   not the pull request’s head: `pgrep` lists one server, now started on the tree link,
   and the ref selector names `main`.
3. **A ref with a `/`.**
   `open -b "$APP_ID" "$REPO/blob/claude/app-open-urls/docs/macos-app.md"` (any branch
   whose name holds a `/` that GitHub still has) shows that file on that branch, not a
   missing page.
4. **Asked before a clone.** With a small public repository you have never opened, which
   the cache does not hold, `open -b "$APP_ID" URL` shows one confirmation naming it,
   whose default button, which Return presses, is Cancel; Cancel opens nothing and
   starts no `metab` serving it, and sending it again asks again.
   A repository the cache holds, as in check 2, opens with no question.
5. **Refusals.** `open -b "$APP_ID" "$REPO/issues/1"` shows `metab`’s message about
   issues pages; `open -b "$APP_ID" https://example.com/` and
   `open -b "$APP_ID" "https://user:secret@github.com/jlevy/metabrowser"` show the app’s
   own, which leaves out `user:secret@`. None opens a window, and
   `log show --last 2m --predicate "subsystem == '$APP_ID'"` prints none of those links
   in full.
6. **A burst.**
   `open -b "$APP_ID" $(for n in $(seq 1 30); do echo "$REPO/issues/$n"; done)` sends
   thirty links at once, and one alert says that 30 links could not be opened, and that
   those past one being resolved and `LinkQueue.limit` waiting were never read, rather
   than thirty alerts.
7. **A first clone.** A link to a public repository that is not cached and takes longer
   than `SupervisorPolicy.startupTimeout` to clone keeps its window starting while the
   log grows, then opens.
   While it clones, `open -a "$APP" "$(mktemp -d)"` opens a folder at once, and a link
   to a second repository opens a window that says it waits for another repository’s
   start.
8. **Retry after a quiet start.** Start a clone of the same uncached repository with
   `metab URL --no-serve` in Terminal, then send its link: after
   `SupervisorPolicy.startupTimeout` the window says the server wrote nothing; once the
   Terminal clone ends, Retry opens it from the cache.
9. **Launched by a link.** Quit the app, then `open -b "$APP_ID" "$REPO"`: the app
   starts and opens the repository’s window, and no Open panel appears over it.
10. **No runtime yet.** In Settings, choose a file that is not a `metab`, then send a
    link: Settings says no `metab` is usable and no window opens; choose this checkout’s
    `.venv/bin/metab`, and the link opens.
11. **A `metab` without `--present`.** Choose a `metab` built before `--present`, such
    as one from a checkout of `main` before #540: Settings calls it too old, “built
    before --recent”, the newest flag the app needs, before any link is sent.
12. **Not restored.** Merge a folder window and the repository’s window into one tab
    group with the repository’s tab shown, quit, and launch: the group comes back in its
    place among the windows, showing the folder’s tab, without the repository’s.
13. **The same link twice during a first clone.** Send the link of a repository the
    cache does not hold, choose Clone and Open, and send the same link again while it
    clones: no second question, and once the clone ends the window shows the link, and
    the repository’s log has one `started pid` line since the first.
14. **A link into an open repository during another’s clone.** With `$REPO`’s window
    ready, start a first clone of another repository as in check 7, then send
    `$REPO/pull/517`: `$REPO`’s other tabs keep working, the window the link brought
    forward says it waits for another repository’s start, and once the clone ends it
    starts again and shows the pull request.
15. **A branch the copy lacks.** Push a new branch to a repository you own whose window
    is open, then send its `tree/BRANCH` link: the window shows the default branch, then
    the branch once `metab` has fetched it, with no alert.
    Then send `$REPO/tree/no-such-branch`: the window stays on the default branch, and
    an alert names the repository and the branch the windows show.
16. **Cancel with more links waiting.** Send, at once, the links of a pull request and
    two of its files in a repository the cache does not hold, and a link into `$REPO`:
    one question appears, `$REPO`’s window comes forward while it waits, and after
    Cancel one alert says that 2 more links into the repository were not opened.
    With `$REPO/issues/1` added to the burst, the one alert is titled for 3 links.
17. **Restart Server during another’s clone.** With `$REPO`’s window opened from
    `$REPO/pull/517` and moved on to one of its files, start a first clone of another
    repository as in check 7, then choose File > Restart Server in that window: it says
    it waits for another repository’s start, and `$REPO`’s other tabs keep working.
    Send `$REPO/pull/517` again: the window still says it waits, and once the clone ends
    it shows the pull request, not the file.
    Then, during a third repository’s first clone, choose Restart Server again and send
    `$REPO/tree/main`: the window the link brought forward says it waits.
18. **Recents.** After check 1, File > Open Recent and the Dock icon’s menu list the
    repository first, and `metab --recent`, run with the `metab` the app uses, lists it
    as a `mirror` at `$REPO`. Open a folder, then send `$REPO/tree/main` while the
    repository’s window is open: the repository is listed first again.
    Choosing it in Open Recent opens it as a link to `$REPO` does: its window comes
    forward and starts again on the default branch.

## Print and Drops

`node webkit-gate/run.mjs --checks`, from `apps/macos`, scripts these in the app’s web
view class; this is the same check on the built development app, with a folder holding a
Markdown file open:

1. **The page’s Print button.** At the top right of the Markdown document it calls
   `window.print()`, which opens the same print panel as File > Print; pressing it again
   while the panel is open does nothing.
2. **File > Print.** The print panel shows the document alone, without the shell.
3. **A folder dragged from Finder onto the page** opens in a window of its own.
4. **A file dragged onto the page** opens at its page, in the open folder that holds it
   or else in its own folder.

## Presenting From metab

`metab ROOT --present` hands the app a target with `open -b`
([Presenting to the App](../architecture/arch-cli.md#presenting-to-the-app)); its
goldens use a recording stand-in, so these are the checks that a real app receives what
the report says. Use a `metab` built from this checkout, with the development build
registered (opened once) and every other copy quit.
The build must declare `MetabrowserOpensURLs`, which the app gains with
[#539](https://github.com/jlevy/metabrowser/pull/539): a build without it receives
nothing, so run these once a build with both changes exists, before either is released.
The build stays where `make macos-app` leaves it, so `present` sets
`METABROWSER_ALLOW_UNINSTALLED_APP=1`, which lifts `--present`’s install-location check
for a developer; `make macos-run` launches the app with `open -a` and runs no
`--present`, so it needs no such setting.

```shell
APP_ID=io.github.jlevy.metabrowser.dev
folder="$(mktemp -d)" && mkdir -p "$folder/docs" && echo '# Guide' > "$folder/docs/guide.md"
present() {
  METABROWSER_ALLOW_UNINSTALLED_APP=1 \
    /usr/bin/time -p metab "$@" --present --app-bundle-id "$APP_ID" --format json
}
```

1. **A folder.** `present "$folder"` exits 0 with `delivered_to: app` and `bundle_path`
   naming the development build, and a window opens on the folder.
   Note the `real` time with the app running and again after a quit (a cold start),
   beside `OPEN_TIMEOUT_S` in `cli/present.py`.
2. **A file, its root not open.** Close the folder’s windows, then
   `present "$folder" --path docs/guide.md`: one window opens, rooted at `$folder` (its
   title is the folder’s name, not `docs`), showing `guide.md`.
3. **A file, its root open.** With that window open, the same command shows the file in
   it and opens no second window.
4. **A file, a folder inside its root open.** Open `$folder/docs` on its own
   (`present "$folder/docs"`), then `present "$folder" --path docs/guide.md`: the file
   shows in the `docs` window, the limit the guide states.
5. **A file named alone, a folder above its repository open.** Make `$folder` a
   repository (`git -C "$folder" init`), open the folder that holds it
   (`present "$(dirname "$folder")"`), then `present "$folder/docs/guide.md"`: the file
   opens in a window of its own folder, `docs`, never in the window of the folder above
   the repository, as
   [Open Modes](../architecture/arch-open-modes.md#what-keys-on-the-root) requires.
   With `$folder` open as well, it shows in `$folder`’s window.
6. **A build without the marker.** With a build from before `MetabrowserOpensURLs` (or
   the key deleted from a copy’s `Info.plist` and the copy opened once),
   `present https://github.com/jlevy/metabrowser` exits 4 with `app_not_marked`, and so
   does `present "$folder"`; nothing opens.
7. **A GitHub URL.** With a build that declares the marker,
   `present https://github.com/jlevy/metabrowser/pull/517` opens the pull request’s
   page, as the GitHub Links checks do with `open -b`.
8. **Inside an agent’s sandbox.** From an agent session whose sandbox is on,
   `metab "$folder" --present` exits 5 with `lookup_failed` or `open_failed`, never
   `app_not_found`. Record which, and what the reason says.
9. **An older copy running.** With a build without the marker running and a newer one
   registered, `present https://github.com/jlevy/metabrowser`: record which copy takes
   the URL and whether a window shows it, since the marker is read from the bundle
   LaunchServices prefers, not from the running copy.
10. **Not installed.** `metab "$folder" --present --app-bundle-id "$APP_ID"`, without
    the setting, exits 4 with `app_not_installed`, naming the build’s path under
    `apps/macos/build/` and the two install locations, and asking for nothing to be done
    with that build; nothing opens.

## Setup Flows

What a new user sees first is a window, which no unit test reaches.
`scripts/check-setup-flows.sh` sets up each case on the built development app, says what
to look for, and waits for Return between steps:

```shell
make install && make macos-app   # at the repository root
cd apps/macos
scripts/check-setup-flows.sh no-metab
scripts/check-setup-flows.sh old-metab
scripts/check-setup-flows.sh disk-image
```

Each run copies the app under its own bundle identifier and its own name, so it never
touches the development app’s saved runtime, recents, or LaunchServices entry, nor the
saved session the development app and a release share; the script’s header says how.
It opens the copy with a scratch `HOME`, which hides only what is under it: discovery
and the first-run screen still look in the Homebrew prefixes and on the login shell’s
`PATH`, which with a scratch `HOME` is the system’s own (`/etc/paths` and
`/etc/paths.d`). So the script refuses to run where a `metab` in any of those would be
found, and `no-metab` also where a uv in one would; on a Mac with Homebrew’s uv,
`no-metab` cannot run, and `old-metab` covers the screen with uv.
It downloads and installs nothing: “installing” uv or `metab` links the uv on `PATH` and
this checkout’s `.venv/bin/metab` into the scratch `~/.local/bin`. On exit it quits the
copy with SIGTERM, detaches its image, unregisters the copy, and deletes its defaults,
saved session, and recents.
A copy that needs SIGKILL, a server left running, and a server started from the older
`metab` in `old-metab` are each a failed check: the script finishes its cleanup, then
exits nonzero. `scripts/test-scripts.sh` checks that accounting on stand-in processes.

| Case | What it checks |
| --- | --- |
| `no-metab` | No uv and no `metab`: the uv install and the source checkout step are shown, then only the checkout step, still for a new Terminal window, once uv appears, then the waiting folder opens by itself once `metab` does |
| `old-metab` | A stand-in below the floor (`scripts/setup-check/metab-0.12.0`): the checkout step naming it and no server (the script checks); replacing it opens the folder by itself; a wrapper reporting a newer version under the running server brings the restart offer, and Restart Servers reloads the window on a new port |
| `disk-image` | The copy on a read-only image of its own shows “Move Metabrowser to Applications”, naming the image |

A choice rejected during the first search is checked by hand within `no-metab`, whose
search waits on the login shell: as soon as the copy opens, Settings > Choose metab… and
`/bin/ls`. Settings names the rejection and goes on looking, then shows the steps, and
the waiting folder still opens by itself once `metab` appears.

Not covered: a translocated launch, which needs a quarantined copy that Gatekeeper
accepts, and so a Developer ID build; its detection is tested on the path
(`LaunchLocationTests`).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
