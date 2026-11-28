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

**Keep the checks out of your own recent targets.** The app records every folder and
repository it opens, and the Recents check clears the list.
So run every check against a scratch configuration directory: export it in the shell, so
that a `metab` run there reads and writes its list, and launch the app with it, which
passes it on to every `metab` the app runs (`ChildEnvironment`):

```shell
export METABROWSER_CONFIG_DIR="$(mktemp -d)/config"
dev_open() { open --env METABROWSER_CONFIG_DIR="$METABROWSER_CONFIG_DIR" "$@"; }
```

`dev_open` is `open` that gives a launched app that directory; `open` gives one the
environment LaunchServices has, not the shell’s. The checks below open the app and send
it links with it, since a link may launch the app, and `--env` changes nothing for a
copy already running.
Wherever one quits the app and launches it again, launch the development build with
`dev_open`, never from the Dock or Finder: a copy launched any other way reads and
writes your own list and `config.yml`. `make macos-run` starts the app with
`METABROWSER_RECORD_RECENT=0`, which records nothing, so the Recents and Switching
Folders checks cannot pass under it.
Note what `env -u METABROWSER_CONFIG_DIR metab --recent` lists, your own list, which the
checks leave as it was.

## Servers and the Runtime

```shell
app="$PWD/apps/macos/build/dev/Metabrowser.app"
logs="$HOME/Library/Logs/Metabrowser"
folder="$(mktemp -d)"
```

1. **Which build.** `dev_open -a "$app" "$folder"`, then Metabrowser > About
   Metabrowser. Below the version is “Development build · VERSION (BUILD) · COMMIT”, the
   commit with `-dirty` for uncommitted changes.
   The Dock shows the canary icon, and Help > Reveal Logs Folder opens `$logs`.
2. **Health check.** With the folder open, find its server (`pgrep -f -- "--no-open"`)
   and stop it without ending it: `kill -STOP PID`. Bring the folder back (Command-click
   a link in it, or open the folder again).
   Within `SupervisorPolicy.healthDeadline` and then `shutdownGrace` (a stopped process
   holds SIGTERM until SIGKILL ends it), the window says “The server stopped answering”
   and offers Retry, and Retry serves the folder again.
   Done with a Command-click, the new window shows the clicked page after Retry, not the
   folder’s first page.
   With the server answering,
   `printf 'a\n' > "$folder/a.md"; printf 'b\n' > "$folder/b.md"` and
   `dev_open -a "$app" "$folder/a.md" "$folder/b.md"` end on `b.md`.
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
   `dev_open --env METABROWSER_METAB=/tmp/metab -a "$app"`. Settings > Runtime > Places
   looked lists `/tmp/metab` as not run because `/private/tmp` can be changed by every
   account, the log says “not running /tmp/metab”, and the runtime is not 9.9.9. Choose
   metab… and `/tmp/metab` then uses it, saying it runs because you chose it.
   `rm /tmp/metab` and forget the saved runtime again afterward.

## Files, Windows, Recents, and Restore

Set `APP` to the development build and make some folders:

```shell
APP="$PWD/apps/macos/build/dev/Metabrowser.app"
LOGS="$HOME/Library/Logs/Metabrowser"
mkdir -p /tmp/mb-check/{a/sub,b,c,d,e,f,g,h,.hidden} "$HOME/Documents/mb-check"
echo '# notes' > /tmp/mb-check/a/notes.md; echo '# deep' > /tmp/mb-check/a/sub/deep.md
log stream --predicate 'subsystem == "io.github.jlevy.metabrowser.dev"' &  # the app log
```

1. **A file.** `dev_open -a "$APP" /tmp/mb-check/a/notes.md` opens a window for `a`
   showing `notes.md`. `dev_open -a "$APP" /tmp/mb-check/a/sub/deep.md` shows `deep.md`
   in that same window, and `pgrep -fl 'metab /private/tmp/mb-check'` still lists one
   server. `dev_open -a "$APP" /dev/null` shows an alert.
   File > Open Folder… chooses a file too.
2. **Recents.** After opening `b`, File > Open Recent and the Dock icon’s menu list `b`
   above `a`, and `metab --recent`, run in this shell with the `metab` the app uses,
   lists the same two. After `metab /tmp/mb-check/h --no-open` in this shell, stopped
   with Control-C, and a switch back to the app, File > Open Recent lists `h` first.
   Opening `a` again, while its window is open, moves it to the top.
   **One list in the Dock:** drop `f` on the Dock icon, run
   `dev_open -a "$APP" /tmp/mb-check/g`, which opens it as Finder’s Open With does, and
   choose `b` with File > Open Folder…. The Dock icon’s menu then lists each folder
   exactly once, in the order File > Open Recent shows, with nothing but separators
   between that list and the app’s own items, and choosing `g` in it brings `g`’s window
   forward. A folder listed twice, or a second group of folders, is macOS’s own
   recent-documents list beside the app’s, and fails the check: the app clears macOS’s
   list only once, at launch, and would have to clear it after each open.
   Close the windows of `f` and `g`. After `rm -r /tmp/mb-check/h`, choosing `h` shows
   the alert and removes it.
   **Not opens:** quit, and relaunch with `dev_open -a "$APP"`, which restores `a` and
   `b`: both menus and `metab --recent` list what they did before the quit, in the same
   order, and the Dock menu lists no folder twice.
   Click `a`’s window, minimize every window, and click the Dock icon: `a`’s window
   comes forward, and the order is still the same, `b` above `a`. Clear Menu then
   empties both menus and `metab --recent`, and your own list,
   `env -u METABROWSER_CONFIG_DIR metab --recent`, is as it was before the checks.
   `defaults read io.github.jlevy.metabrowser.dev` shows no `recentFolders` key.
3. **A window per folder.** Opening `c` and `d` gives each a window of its own.
   With System Settings > Desktop & Dock > “Prefer tabs when opening documents” at
   Always, opening `e` gives it a window of its own too.
   The Window menu has no Merge All Windows, Show All Tabs, or Move Tab to New Window,
   the View menu no Show Tab Bar, and Settings > General no Open folders in.
   After `defaults write io.github.jlevy.metabrowser.dev newFolderPlacement tabs`, as an
   earlier build saved it, a relaunch and opening `f` still give `f` a window of its
   own. Run `defaults delete io.github.jlevy.metabrowser.dev newFolderPlacement`
   afterward.
4. **Discarded pages.** In `a`’s window, use the Switch Folder panel to choose `b`, `c`,
   `d`, and `e` in turn, so the folders left behind stay open in the background: once
   more folders are in the background than
   `PageDiscardPolicy.defaultLiveBackgroundPages`, the app log says “discarding the
   background page of” the folder shown longest ago, and
   `ps -axo pid,command | grep -c '[W]ebContent'` drops by one.
   Switching back to that folder reloads its page, with no “Starting” text, at the top
   of the page and with no Back or Forward history, since a discarded page keeps only
   its address. A minimized window keeps its page however many folders are in the
   background.
5. **Restore.** With windows for `a`, `b`, and `c`, `b`’s in front and `a`’s at the
   back, quit. `session.json` in `~/Library/Application Support/Metabrowser/` now lists
   them; the next launch logs “restoring 3 window(s)” with 3 servers to start, the
   windows come back, and `grep -h 'started pid' "$LOGS"/{a,b,c}-*.log` with its
   timestamps shows `b` started first, then `c`, then `a`, each after the one before it
   was ready. **From an earlier build:** quit, then replace the file with one window of
   tabs, as an earlier build saved it:
   `printf '{"windows":[{"tabs":[{"root":"/private/tmp/mb-check/a"},{"root":"/private/tmp/mb-check/b"}],"selected":1}]}' > "$HOME/Library/Application Support/Metabrowser/session.json"`.
   The next launch opens a window for `a` and one for `b`, `b`’s in front with its page
   loaded, and `a`’s page loads when its window is brought forward.
6. **Protected locations.** Open `~/Documents/mb-check` in a window behind the others,
   quit, and launch again: its window says “Metabrowser opens mb-check when you bring it
   forward.”, and `pgrep -fl 'Documents/mb-check'` finds no server until you do.
   Once Documents access is granted, no prompt appears either way.
   To see that the restore raises none, the person at the Mac first resets that grant
   (`tccutil reset SystemPolicyDocumentsFolder io.github.jlevy.metabrowser.dev`) and
   then checks that the prompt waits until the window is brought forward: the waiting
   window still shows the folder’s name and icon, and whether reading those can prompt
   is untested.
7. **A folder replaced by a link.** With `d` in a window behind `a`’s and `e` not open,
   quit, then
   `mv /tmp/mb-check/d /tmp/mb-check/d-old; ln -s /tmp/mb-check/e /tmp/mb-check/d`, and
   launch: `d`’s window says “Metabrowser opens d when you bring it forward.”
   Bring it forward: the app log says it “now leads to /private/tmp/mb-check/e”, the
   window shows `e`, and `dev_open -a "$APP" /tmp/mb-check/e` and
   `dev_open -a "$APP" /tmp/mb-check/d` bring that window forward, while
   `pgrep -fl 'metab /private/tmp/mb-check/[de]'` lists one server, for `e`. Put `d`
   back with `rm /tmp/mb-check/d; mv /tmp/mb-check/d-old /tmp/mb-check/d`.
8. **Off, and empty.** With Settings > General > “Reopen the last session’s folders when
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
    choose `sub` with File > Open Folder…. Note which folder the window names, how many
    prompts appear and for which folder, and that the tree lists the repository’s root
    once access is granted.
    Repeat with the repository in `~/Desktop` and in `~/Downloads`. How macOS treats a
    served root above the folder chosen in the open panel is untested.
11. **View on GitHub.** Open a checkout of a repository on github.com whose commit is
    pushed, such as this repository, and open `README.md`. The header’s upper right
    holds the GitHub mark, “View on GitHub”, and a chevron.
    Click View on GitHub: a popover below the button shows `README.md` on github.com at
    the commit, and the window behind it still shows Metabrowser’s view
    ([View on GitHub](#view-on-github) checks the popover).
    Open the chevron’s menu: Copy Link puts the same address on the clipboard; Open in
    Browser opens it in the default browser, and no popover opens.
    The same button is in the same place on a folder, a pull request’s page, and a
    commit’s page. A file you have edited and not committed shows none, and a folder with
    no GitHub remote shows none and leaves no gap for one.
12. **Hidden folders.** In File > Open Folder…, press Command-Shift-G and go to
    `/tmp/mb-check`: the panel lists `.hidden` without Command-Shift-Period, and
    choosing it opens it.
    Command-Shift-Period hides the hidden folders, and pressed again shows them.

## GitHub Links

With the development build running a `metab` from this checkout, and `gh` signed in:

```shell
APP="$PWD/apps/macos/build/dev/Metabrowser.app"
APP_ID=io.github.jlevy.metabrowser.dev
REPO=https://github.com/jlevy/metabrowser
# The repository's log: its name, then 8 hex digits of its URL's SHA-256 (ServerLog).
LOG="$HOME/Library/Logs/Metabrowser/metabrowser-$(printf %s "$REPO" | shasum -a 256 | cut -c1-8).log"
```

1. **A pull request.** `dev_open -b "$APP_ID" "$REPO/pull/517"` opens a window at the
   pull request’s page, titled for the repository until the server answers and then as
   `metab` names the pull request.
   If the cache did not hold the repository, a confirmation named
   `github.com/jlevy/metabrowser` came first.
   `pgrep -fl -- "metab $REPO/pull/517"` lists one server, on a port from
   `CLIServeLaunch.repositoryBasePort` up, and `"$LOG"` holds its clone or cache line.
2. **Another revision of an open repository.** `dev_open -b "$APP_ID" "$REPO/tree/main"`
   brings that window forward, which says it is starting and then shows `main`’s tree,
   not the pull request’s head: `pgrep` lists one server, now started on the tree link,
   and the ref selector names `main`.
3. **A ref with a `/`.**
   `dev_open -b "$APP_ID" "$REPO/blob/claude/app-open-urls/docs/macos-app.md"` (any
   branch whose name holds a `/` that GitHub still has) shows that file on that branch,
   not a missing page.
4. **Asked before a clone.** With a small public repository you have never opened, which
   the cache does not hold, `dev_open -b "$APP_ID" URL` shows one confirmation naming
   it, whose default button, which Return presses, is Cancel; Cancel opens nothing and
   starts no `metab` serving it, and sending it again asks again.
   A repository the cache holds, as in check 2, opens with no question.
5. **Refusals.** `dev_open -b "$APP_ID" "$REPO/issues/1"` shows `metab`’s message about
   issues pages; `dev_open -b "$APP_ID" https://example.com/` and
   `dev_open -b "$APP_ID" "https://user:secret@github.com/jlevy/metabrowser"` show the
   app’s own, which leaves out `user:secret@`. None opens a window, and
   `log show --last 2m --predicate "subsystem == '$APP_ID'"` prints none of those links
   in full.
6. **A burst.**
   `dev_open -b "$APP_ID" $(for n in $(seq 1 30); do echo "$REPO/issues/$n"; done)`
   sends thirty links at once, and one alert says that 30 links could not be opened, and
   that those past one being resolved and `LinkQueue.limit` waiting were never read,
   rather than thirty alerts.
7. **A first clone.** A link to a public repository that is not cached and takes longer
   than `SupervisorPolicy.startupTimeout` to clone keeps its window starting while the
   log grows, then opens.
   While it clones, `dev_open -a "$APP" "$(mktemp -d)"` opens a folder at once, and a
   link to a second repository opens a window that says it waits for another
   repository’s start.
8. **Retry after a quiet start.** Start a clone of the same uncached repository with
   `metab URL --no-serve` in Terminal, then send its link: after
   `SupervisorPolicy.startupTimeout` the window says the server wrote nothing; once the
   Terminal clone ends, Retry opens it from the cache.
9. **Launched by a link.** Quit the app, then `dev_open -b "$APP_ID" "$REPO"`: the app
   starts and opens the repository’s window, and no Open panel appears over it.
10. **No runtime yet.** In Settings > Runtime, choose a file that is not a `metab`, then
    send a link: Settings says no `metab` is usable and no window opens; choose this
    checkout’s `.venv/bin/metab`, and the link opens.
11. **A `metab` without `--present`.** Choose a `metab` built before `--present`, such
    as one from a checkout of `main` before #540: Settings calls it too old, “built
    before --recent”, the newest flag the app needs, before any link is sent.
12. **Not restored.** With a folder window and the repository’s window open, quit and
    launch: the folder’s window comes back, without the repository’s.
13. **The same link twice during a first clone.** Send the link of a repository the
    cache does not hold, choose Clone and Open, and send the same link again while it
    clones: no second question, and once the clone ends the window shows the link, and
    the repository’s log has one `started pid` line since the first.
14. **A link into an open repository during another’s clone.** With `$REPO`’s window
    ready, start a first clone of another repository as in check 7, then send
    `$REPO/pull/517`: `$REPO`’s other windows keep working, the window the link brought
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
    it waits for another repository’s start, and `$REPO`’s other windows keep working.
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
19. **A first clone’s progress.** Send the link of a public repository the cache does
    not hold that takes several `MetabAcquisition.progressLineInterval` to clone, such
    as `https://github.com/git/git`, and choose Clone and Open.
    Under “Starting Metabrowser for git…”, the window says “Cloning into
    ~/.cache/metabrowser”, then a line such as “Receiving objects: 45%, 334.0 MiB at 9.5
    MiB/s (40 s)” that changes about once an interval, then a line such as “Cloned in 44
    s (311.2 MiB); starting the server”, and then shows the repository.
    A pull request link into a repository the cache does not hold ends with “Reading
    pull request N (… s)” while GitHub answers slowly enough to show it.
    A folder’s window never shows such a line.
20. **Not found, or not readable.** Send
    `https://github.com/jlevy/no-such-repository-here` and choose Clone and Open.
    The window says “Not found, or this account cannot read it”, shows `metab`’s
    message, which names `not_found_or_private`, and three commands, `gh auth status`,
    `gh auth login`, and `gh auth refresh … --scopes repo`, each of whose Copy buttons
    copies that command alone, and says that Metabrowser tries again when you switch
    back to it. Copy Message copies “Metabrowser could not open
    github.com/jlevy/no-such-repository-here: Not found, or this account cannot read
    it.”, the message, and the three commands; the server’s output is under “Recent
    server output”.
21. **Signed out, then back from Terminal.** Note the account `gh auth status` names,
    then `gh auth logout --hostname github.com`, and send the link of a private
    repository that account can read, which the cache does not hold.
    The window shows the failure of check 20, since a clone cannot tell a signed-out
    `gh` from a missing repository, and its first command, run in Terminal, says no
    account is signed in.
    Run `gh auth login --hostname github.com` in Terminal and switch back to the app:
    the window starts again by itself, shows the clone’s progress, and opens the
    repository, and
    `log show --last 5m --predicate "subsystem == '$APP_ID'" | grep "on activation"`
    lists one start again after `not_found_or_private`.
22. **No GitHub CLI.** Move `gh` aside
    (`mv "$(command -v gh)" "$(command -v gh).aside"`), choose Refresh in Settings >
    Runtime, whose gh row then says not found, and send the link of a private repository
    the cache does not hold.
    The window says “Not found, or private, and Metabrowser did not find GitHub CLI”,
    tells you to check the link or, for a private repository, to install GitHub CLI and
    then choose Refresh, and offers `gh auth login --hostname github.com`; it does not
    say that switching back tries again, and switching to another app and back leaves
    the failure as it is.
    Move `gh` back, choose Refresh, and press Retry: the repository opens.
23. **No connection.** Turn Wi-Fi off and send the link of a public repository the cache
    does not hold. The window says “The connection to GitHub failed”, with `metab`’s
    message, which names `network_unreachable`, and
    `metab https://github.com/OWNER/REPO --no-serve` to copy, and does not say that
    switching back tries again.
    Turn Wi-Fi on, then switch to another app and back: the failure stays, since a
    network failure can come minutes into a clone that a retry would fetch from zero.
    Press Retry: the repository opens.
24. **Only failures a sign-in can fix start again.** With a folder whose server failed,
    as in check 2 of [Servers and the Runtime](#servers-and-the-runtime), a repository
    that could not connect, as in check 23 before its Retry, and a repository’s window
    that is ready, switch to another app and back: the first two still offer Retry, the
    ready repository’s page does not reload, no `pgrep -fl -- "--no-open"` pid changes,
    and the `log show` command of check 21 lists no new start again.

## File > Open URL…

With `APP_ID`, `REPO`, and `LOG` set as in [GitHub Links](#github-links), and the same
build, `metab`, and `gh` sign-in.
What the panel decides is unit-tested in `OpenURLPanelTests`, and against the real
`metab` in `LiveMetabTests`; these check what AppKit does with it.

1. **The menu.** The File menu reads Open Folder… (Command-O), Open URL… (Command-L),
   then Open Recent. Command-L with a folder’s page focused, with a repository’s page
   focused, and with no window open shows a panel titled Open URL with its field
   focused. The three examples beneath the field read
   `https://github.com/jlevy/metabrowser`, `github.com/jlevy/metabrowser`, and
   `jlevy/metabrowser`. Command-L again brings the same panel forward.
2. **A pull request.** Paste `$REPO/pull/517` and press Return: the panel closes, and
   the pull request opens as GitHub Links check 1 opens it, in the repository’s mirror:
   `pgrep -fl -- "metab $REPO/pull/517"` lists one server, and the title’s tooltip says
   it is a cached mirror.
   With a checkout of this repository also open as a folder, Open URL… `$REPO/tree/main`
   brings the mirror’s window forward on `main`, never the checkout’s.
3. **Each kind.** `$REPO`, `$REPO/tree/main/docs`, `$REPO/blob/main/README.md`, and
   `$REPO/commit/dcf2bcfa8` each bring the repository’s window forward at that page, as
   GitHub Links check 2 does.
4. **The app’s refusals.** `./jlevy/metabrowser`, `jlevy/metabrowser#517`,
   `gitlab.com/jlevy/metabrowser`, `git@github.com:jlevy/metabrowser.git`,
   `http://gitlab.com/jlevy/metabrowser`,
   `https://user:secret@github.com/jlevy/metabrowser`,
   `https://github.com:8443/jlevy/metabrowser`, and
   `https://gitlab.com/jlevy/metabrowser` each show a reason under the field, with no
   alert and no window; the panel stays open with the text, editing it clears the
   reason, and `log show --last 2m --predicate "subsystem == '$APP_ID'"` has no
   `Open URL…` line for any of them, since no `metab` ran.
5. **The repository URL is written in full.** `github.com/jlevy/metabrowser`,
   `jlevy/metabrowser`, `http://github.com/jlevy/metabrowser`, and
   `//github.com/jlevy/metabrowser` each show `https://github.com/jlevy/metabrowser` in
   the field when Return is pressed, all of it selected and the field still focused,
   with no message, and open the repository as check 3 does.
   `github.com/jlevy/metabrowser/issues/1` shows
   `https://github.com/jlevy/metabrowser/issues/1` in the field, selected, and `metab`’s
   message about issues pages under it.
6. **`metab`’s refusals.** `$REPO/issues/1` shows `metab`’s message about issues pages,
   and `$REPO/pull/0` its message about pull request numbers, under the field, with no
   alert and no window, and never JSON or a traceback; then editing the text to
   `$REPO/pull/517` and pressing Return opens it.
7. **Cancel.** Escape, the Cancel button, the close button, and File > Close Window
   (Command-W) each close the panel and open nothing, and close no window behind it.
   The panel comes back empty.
8. **A repository the cache does not hold.** A small public repository you have never
   opened: the panel closes, and the confirmation of GitHub Links check 4 appears.
9. **No runtime yet.** As in GitHub Links check 10, choose a file that is not a `metab`
   in Settings > Runtime, then Open URL… `$REPO`: the panel closes and no window opens;
   choose this checkout’s `.venv/bin/metab`, and the repository opens.
10. **Editing.** Command-V and Edit > Paste paste into the field, and Command-A selects
    its text.
11. **A space in the path.** `$REPO/blob/main/docs/a b.md` closes the panel and brings
    the repository’s window forward at the `handoff` that
    `metab "$REPO/blob/main/docs/a b.md" --present --dry-run --format json` prints,
    `docs/a%20b.md`, which the mirror reports missing.
    `$REPO/blob/main/README`, then U+3164 HANGUL FILLER pasted from a character viewer,
    then `.md`, shows a reason that names U+3164 and `%E3%85%A4` under the field, and no
    window opens.

## View on GitHub

With the development build open on a checkout of this repository at a pushed commit,
`README.md` shown, and `APP_ID` and `REPO` set as in [GitHub Links](#github-links).
Start signed out: choose Metabrowser > Clear Website Data…, All Websites, and Clear.

1. **The popover.** Scroll `README.md` a little, then click View on GitHub.
   A popover opens below the button, pointing at it, over most of the window, with a
   one-line header: Back, Forward, `github.com/jlevy/metabrowser/blob/COMMIT/README.md`
   in gray, with `COMMIT` the checkout’s commit, Copy Link, and Open in Browser.
   Behind it, the page has not moved.
   Escape closes it; open it again and Command-W closes it, not the window; open it
   again and a click on the page outside it closes it.
   Make the window larger and open it again: the popover is larger.
2. **It keeps its place for a while.** In the popover, follow a link to `docs/` on
   github.com, close the popover, and open it again at once: it is still at `docs/`, and
   Back returns to `README.md`. Close it, wait longer than
   `WebPaneState.keptAfterClosing`, and open it: it loads `README.md` again, with Back
   dimmed. Open `CHANGELOG.md` in the page and click View on GitHub: the popover shows
   `CHANGELOG.md`. Turn Wi-Fi off, open `CHANGELOG.md`’s parent folder in the page, and
   click View on GitHub: the header says the page did not load.
   Turn Wi-Fi on, close the popover, and open it again: the folder loads; do it again
   offline and press Command-R once back online: it loads too.
   On a pull request, type a comment without sending it, close the popover, wait longer
   than `keptAfterClosing`, and open it: the comment is still there.
3. **The header and the menus.** With the popover open, Command-[ and Command-] go back
   and forward in it, Command-R reloads it, and Command-+ zooms it; Command-0 returns it
   to actual size. The page behind keeps its own zoom, and a new window opens at the
   page’s remembered zoom, not the popover’s. File > Print and Edit > Find are dimmed.
   The header’s Copy Link puts the shown github.com address on the clipboard; Open in
   Browser opens it in the default browser and closes the popover.
4. **Links, downloads, and drops.** In the popover, a link in the README to another site
   opens in the default browser, and the popover stays where it was.
   Command-click on a github.com link opens it in the default browser.
   A file’s Raw button shows the raw file in the popover, on raw.githubusercontent.com.
   Download ZIP, from the repository’s Code menu, opens the default browser, which
   downloads it. Signed in, drag a screenshot from Finder onto a pull request’s comment
   box in the popover: GitHub attaches it, and Metabrowser opens no folder.
   Click “Paste, drop, or click to add files” under the same box: a file panel opens
   over the popover, which stays open, and the file chosen is attached.
   Edit one of your own comments, change it, and click Cancel: GitHub asks whether to
   discard the change, over the popover, and Cancel there keeps the edit.
5. **Only the button.** With the popover open,
   `dev_open -b "$APP_ID" "$REPO/blob/main/README.md"` brings the window forward at that
   page, and the popover closes.
   A github.com link in a Markdown page, which is not the button, opens in the default
   browser.
6. **Sign in once.** In the popover, sign in to github.com with a password and the
   two-factor code. Open a second folder of a repository on github.com, and click View on
   GitHub in its window: it is signed in.
   Quit Metabrowser, open it again, open `README.md`, and click View on GitHub: still
   signed in. The default browser’s own sign-in did not change.
   Note whether a passkey or a security key is offered and works, and what an
   organization’s single sign-on does; neither is checked yet.
7. **Switching and closing folders.** Open a second checkout of a repository on
   github.com, so two such folders are open, and show the first in a window.
   With the popover open, press Shift-Command-O and choose the second folder: the window
   shows it, and no popover is left over it.
   Click View on GitHub there, go to a pull request in the popover, and type a comment
   without sending it. Switch the window to the first folder and back to the second
   within `WebPaneState.keptAfterClosing`, and click View on GitHub: the comment is
   still there. With the popover open, choose File > Close Folder: the folder closes, and
   the popover with it.
8. **Clear Website Data.** Metabrowser > Clear Website Data… asks first, with a menu of
   All Websites and each site that stored something, `github.com` among them, and Cancel
   the default: Return keeps the sign-in.
   Clear with `github.com` chosen signs you out of GitHub; so does All Websites: an open
   popover reloads, signed out, and so does every other folder’s popover the next time
   it opens, in a window or in the background.
   Metabrowser’s own settings, such as its theme, are unchanged, and so is
   `gh auth status`.

## Switching Folders

**Not yet run.** These steps were written with the folder-switching change and have not
yet been run on a Mac.

```shell
APP="$PWD/apps/macos/build/dev/Metabrowser.app"
mkdir -p /tmp/mb-check/{a,b,c,d}
LONG=/tmp/mb-check/projects/2026/clients/northwind/archive/quarterly-reports
mkdir -p "$LONG"
```

Close every window. Open `$LONG` and close its window, then `c` and close its window,
then `d` and close its window, so all three are recent and none is open.
Then open `a`, then `b`, each with `dev_open -a "$APP" /tmp/mb-check/NAME`, so each has
a window of its own.
Each step starts where the one before it ends.

1. **The title.** Each title reads its folder with a small chevron after it, dim at rest
   and darker under the pointer, where a rounded fill appears behind the title and
   chevron; both dim in a window that is not main, in light and dark mode.
   A long name in a narrow window truncates before the chevron, never under it.
2. **Click and drag.** A click on `a`’s title opens the chooser under it; a drag from
   the title moves the window and opens nothing; Command-click and right-click open the
   path menu; a double-click on the title bar outside the title still zooms.
   Pressing and releasing just above or just below the title’s hover surface opens no
   chooser, and a double-click there does the title bar’s action.
   Dragging the title of a window that is not key, and of a Metabrowser window behind
   another app’s window, moves the window; a click there instead brings the window
   forward and opens the chooser.
3. **The chooser.** In `a`’s window it lists Open (`a` checked, then `b` subtitled “In
   another window”), Recent (starting with `d`, then `c`, subtitled with their paths),
   Open Folder…, Open URL…, Switch Folder… (Shift-Command-O), and Close Background
   Folders, disabled. Each folder shows its kind’s mark, the page’s: a plain folder the
   folder with a dot, a Git checkout the folder with Git’s branch, and a GitHub
   repository among the recent ones the cloud; File > Open Recent and the Dock icon’s
   menu show the same marks on their rows, and the title’s path menu shows the folder’s
   own mark on its first row and the plain folder outline on each folder above it.
   Each row’s mark sits on the line of its name, centered on that line as on Open
   Recent’s one-line rows, never between the name and the subtitle, and the subtitle
   starts under the name, not under the mark: in light and dark mode, on the highlighted
   row as white as its text, and on the checked row, whose check mark stands on the
   name’s line too, level with the name and the mark, in the column AppKit gives a
   check, not between the lines.
   `quarterly-reports`, after `c`, shows its path on one line, cut in the middle with an
   ellipsis, its mark still on the name’s line, and resting the pointer on the row shows
   the whole path in a tooltip.
   Escape closes it.
4. **A folder another window shows.** Choosing `b` in `a`’s chooser brings `b`’s window
   forward and keeps `a` in its window.
   Choosing `b` again leaves one window for `b`.
5. **A recent folder.** Choose `c` in `a`’s chooser.
   A separate window opens on `c`, and `a` keeps its window.
6. **A background folder.** In `c`’s window, open the Switch Folder panel and choose
   `d`, so `c` is open in the background.
   Choose `c` in `d`’s title menu.
   A separate window shows `c`’s page where you left it, with the same server.
   The original window still shows `d`.
7. **Option-Return.** In `a`’s window, select `a` in the Switch Folder panel and press
   Option-Return. Command-W closes the second window, and `a` stays open in its first.
8. **Close Background Folders.** In `c`’s window use the Switch Folder panel to choose
   `quarterly-reports`, leaving `c` in the background.
   Choose Close Background Folders in the title menu.
   It stops `c`’s server and removes it from Open.
   Reopen `c` from Recent.
9. **Close Folder.** In `d`’s window, with no folder in the background, File > Close
   Folder closes the window and stops `d`’s server.
   In `b`’s window, use the Switch Folder panel to reopen `d`. File > Close Folder then
   restores `b` in that window and stops `d`’s server.
10. **Close Folder across windows.** Choose `a` with Option-Return in the Switch Folder
    panel over `a`’s window for a second window on it, and a third the same way, then
    minimize the third. With no folder in the background, File > Close Folder in `a`’s
    first window closes all three of `a`’s windows, leaves `b`’s window showing `b`, and
    stops `a`’s server. Open `a` again and give it a second window and a minimized third
    the same way, then open `c` and use the panel to choose `d`, so `c` is in the
    background. File > Close Folder in `a`’s first window now shows `c` in one of the
    windows that showed `a`, a window on screen before the minimized one, closes the
    others, and stops `a`’s server; no window shows `a`. Then close every window but
    `b`’s, and open `a` again.
11. **Switch Folder…, there and back.** In `a`’s window, choose `c` from the Switch
    Folder panel, so `a` is in the background.
    Shift-Command-O opens the panel over the window, centered a little below its title,
    with an empty field that has the focus.
    It lists `a` first and selected, then `b` subtitled “In another window”, then the
    recent folders, and last `c`, checked.
    Each row shows the page’s folder glyph on the line of its name, as the chooser does,
    the selected row is drawn in the accent color, and the check mark sits at the row’s
    trailing edge, centered on the row.
    Return shows `a` in the same window.
    Shift-Command-O, then Return, shows `c` again.
12. **The panel’s keys.** In `c`’s window press Shift-Command-O, then:
    - Down twice, then Up, selects `b`, the first recent folder, then `b` again; Up on
      the first row and Down on the last stay put.
    - Typing `check/d` lists only `d`, selected.
      Command-Delete clears the field, closes nothing, and lists every row again with
      the first selected.
    - Type `check/d` again and press Tab, then Shift-Tab: the field keeps the focus, and
      Delete still edits it and refilters.
      Command-Delete clears it.
    - Command-click the selected row: it stays selected.
      Click `b`’s row once, then press Return: the panel closes and `b`’s window comes
      forward.
    - Click `c`’s window, press Shift-Command-O, then Escape: the panel closes.
      Shift-Command-O, then Control-O: no window opens; Escape closes the panel.
      Shift-Command-O, then a click in `b`’s window: the panel closes.
13. **A new window from the panel.** In `c`’s window press Shift-Command-O, and
    Option-Return with `a` selected: `a`, which was in the background, moves its page
    into a new window.
14. **Closing from the panel.** In `b`’s window press Shift-Command-O. With the field
    empty and no folder in the background, Command-Delete on the selected first row,
    `a`, closes `a`’s window and stops its server, and the panel stays open, no longer
    listing `a` as open.
    Click `b`’s own row, last and checked, and press Command-Delete: `b`’s window
    closes, and the panel with it.
    In `c`’s window use the Switch Folder panel to choose `d`, so `c` is in the
    background, and press Shift-Command-O; click `d`’s own row, last and checked, and
    press Command-Delete: the window shows `c`, `d`’s server stops, and the panel stays,
    listing `c` checked.
15. **Folders closed under the panel.** In `c`’s window use the Switch Folder panel to
    choose `d`, so `c` is in the background, and press Shift-Command-O. With the panel
    open, choose File > Close Folder in the menu bar: the window shows `c`, and the
    panel stays, listing `c` checked and `d` no longer open.
    File > Close Folder again closes the window, and the panel with it.
16. **Sheets, full screen, and the screen’s edges.** Open `a`. With File > Print…’s
    sheet open over its page, View > Switch Folder… and File > Close Folder are
    disabled, and Shift-Command-O beeps and opens no panel; if a click on the title
    still opens the chooser, choosing a recent folder opens that folder in a separate
    window. Cancel the sheet, choose `a` with Option-Return in the panel for a second
    window on it, and open the print sheet in that window: File > Close Folder in `a`’s
    first window beeps and changes nothing.
    Cancel the sheet and close the second window.
    With the window in full screen (View > Enter Full Screen), Shift-Command-O opens the
    panel over it, in its Space.
    Leave full screen, make the window about 300 points tall, and drag it to the bottom
    of the screen and partly past its right edge: Shift-Command-O opens the panel wholly
    on the screen.
17. **VoiceOver.** With VoiceOver on, the title reads as a pop-up button with the
    folder’s name; VO-Space and VO-Shift-M on it each open the chooser, and VoiceOver
    lands in it and reads the open folder `a` as checked, and the others not; the
    Actions rotor offers Show Path, which opens the path menu.
    In the Switch Folder panel, VoiceOver reads the selected row as the panel opens and
    each time Up, Down, or typing moves the selection: its name, its location or “In
    another window”, and “shown in this window” for this window’s folder.
18. **Restore.** In `a`’s window choose `b`, so `a` is in the background, then quit and
    reopen: `a` is back in the chooser’s Open section, and its server starts only when a
    window shows it (`pgrep -fl 'metab /private/tmp/mb-check/a'` lists nothing until
    then).
19. **No window.** In the window choose `c`, so `a` and `b` are both in the background,
    and close the window, which closes `c`: no window is left.
    A click on the Dock icon brings `b`, the folder shown last, forward in a window.
    Close that window, which closes `b`, then quit and reopen: the saved session held
    only `a`, in the background, and the relaunch brings it forward in a window.
20. **A repository’s title.** Open a GitHub repository, as in
    [GitHub Links](#github-links): a Control-click on its window’s title opens nothing.

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

## Find

`PageFindWebKitTests` runs the searches against a real web view; this checks the bar
itself on the built development app, with this repository’s folder open:

1. **Command-F** opens the bar above the page with the field focused; typing `lefthook`
   selects the `lefthook.yml` row in the navigation pane first, as a browser’s find
   would, and Return moves on to the next match.
2. **Another file.** Open SECURITY.md from the tree, press Command-F, and type
   `supported`: “Supported Versions” is selected.
   Shift-Return goes back a match, and a word that is not there shows “Not Found”.
3. **Command-E** with a word selected on the page, then Command-G, finds that word.
4. **Escape** in the field, or Done, closes the bar and gives the page focus back.

## Menu Actions and Closing a Window

A window shows its folder’s page (`FolderPage`), and the menus’ page actions are
nil-targeted, so they reach the page by two routes
([Windows](../architecture/arch-macos-app.md#windows)): the responder chain while the
focus is in the page, and the window controller while the window itself is first
responder.
What each action does is unit-tested (`PageReloadTests`), but not which object
AppKit sends it to: asking AppKit (`NSApp.target(forAction:to:from:)`) needs a key
window, which a test process gets only by taking the focus from whoever is using the
Mac. Nor is when AppKit releases a window’s controller, which no test watches.
With the folders and the app log from Files, Windows, Recents, and Restore, after its
check 1, so that `a`’s window shows `deep.md`, opened after `notes.md`:

1. **Back, Forward, and Reload.** View > Back
   (Command-[) shows `notes.md`, View > Forward (Command-]) shows `deep.md` again, and
   View > Reload Page (Command-R) reloads it in place.
   Hold Back in the title bar to open the history menu and check that `notes.md` comes
   first, with its file icon.
   Choose that item, then secondary-click Forward and choose `deep.md`. Step Back and
   Forward again with the bare brackets.
   Hold Shift on the page and check that hints appear only on the enabled arrows.
   Type a bracket in Find and confirm that the page stays put.
   Click the title-bar link icon, then paste into a text field and check that it
   contains the address of `deep.md`. Click the address text to verify that the same URL
   is selectable and opens in the default browser.
2. **Find and zoom.** Command-F opens the find bar over the page, typing `deep`
   highlights it, and Command-G moves to the next match.
   Zoom In (Command-=) and Zoom Out (Command-Minus) zoom the page, and Actual Size
   (Command-0) restores it.
3. **The server’s items.** File > Reveal Server Log shows `a`’s log in Finder, File >
   Open in Default Browser opens the page in the default browser, and File > Restart
   Server (Option-Command-R) starts `a`’s server again, after which the window shows
   `deep.md`.
4. **The window as first responder.** Stop `a`’s server without ending it (`kill -STOP`
   the pid `pgrep -f 'metab /private/tmp/mb-check/a'` prints), then Command-click a link
   in the page. The new window, whose page never loads, so it stays first responder, says
   “The server stopped answering” within `SupervisorPolicy.healthDeadline` and then
   `shutdownGrace`. View > Reload Page is enabled there, and Command-R does what Retry
   does: the server starts again, and the window shows the clicked page.
5. **Closing.** Close the new window (Command-W):
   `pgrep -fl 'metab /private/tmp/mb-check/a'` still lists `a`’s server, which the other
   window shows. Close that window too, and within `SupervisorPolicy.shutdownGrace` it
   lists none. Restore, check 5, covers what a quit saves.

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
`present` also passes `--open-in app`, so a target no app takes is refused, as these
checks expect, instead of opening in a browser on a server started for it, as the
default `auto` does; checks 11 and 12 cover `auto`. Launch the build with
`dev_open -b "$APP_ID"` first: `--present` hands a target to the copy that runs, and
launches one with `open -b`, which passes no environment, so a copy it launches gets the
scratch directory only as check 1’s cold start gives it.

```shell
APP_ID=io.github.jlevy.metabrowser.dev
folder="$(mktemp -d)" && mkdir -p "$folder/docs" && echo '# Guide' > "$folder/docs/guide.md"
present() {
  METABROWSER_ALLOW_UNINSTALLED_APP=1 \
    /usr/bin/time -p metab "$@" --present --open-in app --app-bundle-id "$APP_ID" --format json
}
```

1. **A folder.** `present "$folder"` exits 0 with `delivered_to: app` and `bundle_path`
   naming the development build, and a window opens on the folder.
   Note the `real` time with the app running and again after a quit (a cold start),
   beside `OPEN_TIMEOUT_S` in `cli/present.py`. The cold start must not reach your own
   list, where an open of a full list drops its oldest entry for good, so give the
   scratch directory to every app launchd starts for the length of it:
   `launchctl setenv METABROWSER_CONFIG_DIR "$METABROWSER_CONFIG_DIR"`, then the timed
   `present "$folder"`, then `launchctl unsetenv METABROWSER_CONFIG_DIR` as soon as the
   window opens, before you launch anything else.
   The app keeps the directory it started with,
   `launchctl getenv METABROWSER_CONFIG_DIR` prints nothing, and
   `env -u METABROWSER_CONFIG_DIR metab --recent` is still your own list as it was.
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
   page, as the GitHub Links checks do with `dev_open -b`.
8. **Inside an agent’s sandbox.** From an agent session whose sandbox is on,
   `metab "$folder" --present` exits 5 with `lookup_failed` or `open_failed`, never
   `app_not_found`, under the default `auto` too, which starts no server then.
   Record which, and what the reason says.
9. **An older copy running.** With a build without the marker running and a newer one
   registered, `present https://github.com/jlevy/metabrowser`: record which copy takes
   the URL and whether a window shows it, since the marker is read from the bundle
   LaunchServices prefers, not from the running copy.
10. **Not installed.**
    `metab "$folder" --present --open-in app --app-bundle-id "$APP_ID"`, without the
    setting, exits 4 with `app_not_installed`, naming the build’s path under
    `apps/macos/build/` and the two install locations, and asking for nothing to be done
    with that build; nothing opens.
11. **No app, under `auto`.**
    `metab "$folder" --present --app-bundle-id "$APP_ID" --format json`, without the
    setting, exits 0 with `delivered_to: browser`, `code: server_started`, and
    `fallback.code: app_not_installed`; a browser tab opens on the folder at the
    report’s `url`. `kill` with the report’s `pid` stops the server, and the page then
    fails to load.
12. **Browser delivery turned off.** With `present_browser: false` in the `config`
    mapping of the scratch `$METABROWSER_CONFIG_DIR/config.yml`, the command of check 11
    exits 4 with `browser_off`, and so does
    `metab "$folder" --present --open-in browser --format json`; nothing opens and no
    server starts (`pgrep -f metabrowser.cli.main` finds none).
    Remove the line after.

## Settings and Help > Check Setup…

How the app reads `metab --doctor --json` is unit tested (`DoctorReportTests`, which
reads the doctor’s transcript, and `LiveMetabTests` against a real `metab`), and
`SettingsWindowTests` presses the tabs through accessibility and copies part of the
report; these check the window as a person uses it, in light and dark appearance.
Choose the checkout’s `.venv/bin/metab` in Settings > Runtime first.

```shell
real="$PWD/.venv/bin/metab"
stand_in="$HOME/.metab-check-setup"
mkdir -p "$stand_in"
```

1. **The tabs.** Metabrowser > Settings… opens at General, with General, Runtime,
   Plugins, and Check Setup along the toolbar.
   Click each: the window takes the tab’s size with its top edge still, and nothing in a
   tab overlaps. With Full Keyboard Access on, Tab reaches the tabs and the controls in
   order and Space presses them.
   Close the window and choose Settings… again: it opens at the tab it showed last.

2. **The plugins.** Click Plugins: within seconds it lists each plugin of
   `.venv/bin/metab --plugins` with its name, ID, version, source, and what it requires,
   and counts them below.
   Switch tabs and back: the list shows at once, without discovering again.
   Refresh discovers them again.

3. **A clean report.** Help > Check Setup…. Settings comes forward at Check Setup, and
   within seconds it says there are no problems, then shows the report as text: the
   development build, the oldest `metab` it runs, and the checkout’s `metab`, then
   `plugins`, `open_in`, `metab`, `git`, `config`, `cache`, `event_log`, and `github`,
   each `ok`, with nothing overlapping at any window width.
   The `metab` check’s app detail names this development build and the `metab` it runs,
   even with a release app installed too.
   Drag across a few lines in the middle of the report, Command-C, then `pbpaste` prints
   exactly those lines.
   Scroll down a little and Refresh while they are selected: when the new report
   arrives, the same lines are still selected and the report has not moved.
   Copy Report, then `pbpaste` prints the whole report.

4. **A problem with its check.** Choose a stand-in that points the cache somewhere
   `metab` refuses:

   ```shell
   printf '#!/bin/sh\nMETABROWSER_CACHE_DIR=relative exec "%s" "$@"\n' "$real" > "$stand_in/metab"
   chmod 755 "$stand_in/metab"
   ```

   then Settings > Runtime > Choose metab… and `$stand_in/metab`. Settings > Check
   Setup: the heading says `metab` found problems, `cache` is a problem with the
   override’s message, and `plugins` stays ok.

5. **No report.** Replace the stand-in with one whose doctor fails:

   ```shell
   printf '#!/bin/sh\ncase "$*" in\n*--doctor*) echo boom; exit 3;;\nesac\nexec "%s" "$@"\n' "$real" > "$stand_in/metab"
   ```

   and Refresh. The tab says `metab --doctor --json` printed no answer (exit status 3\)
   and shows `boom`; Copy Report includes both.

6. **No metab, then one.** In Settings > Runtime, forget the chosen `metab` so none is
   selected, and in Check Setup, Refresh: the tab says none is selected, Refresh stays
   enabled, and Plugins says no plugins are listed.
   Choose `$real` in Settings > Runtime, then Check Setup: it shows the clean report
   without the Help menu.
   Then `rm -r "$stand_in"`.

## Help > Open Event Log

`EventLogLocation` (what each answer of `metab` does, and where the segment opens) is
unit tested; these check the menu item, the window it opens, and what AppKit and the
server do with it. Run them with the app’s servers writing to the log you will look at:
the checks read it from `$state`, which the app’s servers use because the app passes
`METABROWSER_STATE_DIR` on (`ChildEnvironment`).

```shell
state="${XDG_STATE_HOME:-$HOME/.local/state}/metabrowser/events"
segment() { ls -t "$state"/events-*.jsonl | head -1; }
```

1. **The log opens on its own folder.** Open the home folder, an ancestor of the state
   directory, `dev_open -a "$APP" "$HOME"`, and click through a few files so its server
   answers requests. Help > Open Event Log opens a window whose folder is `events`, at
   the newest segment’s Timeline, and not a page inside the home folder’s window, which
   still shows the home folder.
   The Help item works from either window and from no window.
2. **Not in Open Recent.** File > Open Recent and the Dock icon’s menu list `$HOME`, as
   they did, and not `events`. Quit and reopen the app: `events` is restored with the
   session, as any open folder is, and is still not in Open Recent.
3. **Reading the log writes nothing into it.** Quit every window but `events`’s. Click
   rows open in the Timeline and switch to Latency and Errors, then `wc -c "$(segment)"`
   twice, a few seconds apart: the size is the same, because the server of the log’s own
   directory writes no log.
4. **The home folder’s server skips its reads of the log.** In the home folder’s window,
   open `.local/state/metabrowser/events/` and a segment, switch the segment to Latency,
   and `grep -c 'plugin/event-log' "$(segment)"`: the count does not change between two
   reads of the segment, while a request for another file adds a `request` record.
5. **No log yet.** Quit, and
   `dev_open --env METABROWSER_STATE_DIR="$(mktemp -d)" -a "$APP"`. With no folder open,
   Help > Open Event Log says there is no event log yet and names the directory.
6. **A `metab` that cannot say.** Choose a stand-in that fails for `--api`
   (`printf '#!/bin/sh\ncase "$*" in\n*--api*) echo boom; exit 3;;\nesac\nexec "%s" "$@"\n' "$PWD/.venv/bin/metab" > /tmp/metab-stand-in; chmod 755 /tmp/metab-stand-in`,
   then Settings > Runtime > Choose metab…): Help > Open Event Log says it could not
   open the log, shows `boom`, and points to Check Setup…. Choose the checkout’s `metab`
   again and `rm /tmp/metab-stand-in`.
7. **Turned off.** Quit, then
   `dev_open --env METABROWSER_EVENT_LOG=0 -a "$APP" "$HOME"`. Help > Check Setup… marks
   Event log as a warning that names the variable, and a late wait’s Details on a pull
   request page say the log is off and why, where with the log on they name Help > Open
   Event Log and not the `metab --event-log` command.

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
found, and `no-metab` also where a uv in one would.
Use `old-metab` on a Mac with Homebrew’s uv.
It downloads and installs nothing: “installing” uv or `metab` links the uv on `PATH` and
this checkout’s `.venv/bin/metab` into the scratch `~/.local/bin`. On exit it quits the
copy with SIGTERM, detaches its image, unregisters the copy, and deletes its defaults,
saved session, and recents.
A copy that needs SIGKILL, a server left running, and a server started from the older
`metab` in `old-metab` are each a failed check: the script finishes its cleanup, then
exits nonzero. `scripts/test-scripts.sh` checks that accounting on stand-in processes.

| Case | What it checks |
| --- | --- |
| `no-metab` | Settings shows the minimum and links to the README’s installation guide. Check its uv instructions for a released minimum and its developer preview instructions when the minimum is pending. Places looked lists the places searched, scrolling within the Runtime tab when it is long, and Reveal Logs Folder stays in the window. With only uv installed, Refresh still reports no usable runtime. Once `metab` appears, the waiting folder opens by itself |
| `old-metab` | Settings explains why the stand-in (`scripts/setup-check/metab-0.12.0`) is incompatible. The script checks that no server starts. Replacing the stand-in opens the waiting folder by itself. A wrapper reporting a newer version under the running server brings the restart offer, and Restart Servers reloads the window on a new port |
| `disk-image` | The copy on a read-only image of its own shows “Move Metabrowser to Applications”, naming the image |

A choice rejected during the first search is checked by hand within `no-metab`, whose
search waits on the login shell: as soon as the copy opens, Settings > Runtime > Choose
metab… and `/bin/ls`. Settings names the rejection and goes on looking, then shows the
minimum, and the waiting folder still opens by itself once `metab` appears.

Not covered: a translocated launch, which needs a quarantined copy that Gatekeeper
accepts, and so a Developer ID build; its detection is tested on the path
(`LaunchLocationTests`).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
