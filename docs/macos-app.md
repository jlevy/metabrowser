# The macOS App

The Metabrowser app is an alpha preview built from source;
[Release Status](installation.md#release-status) says what that means today, and
[Installation](installation.md#the-macos-app) says how to build it.

The app is a native shell over `metab`. Everything inside a window is the page `metab`
serves, the same page a browser shows.
What the app adds is what a browser tab cannot give:

- a window per folder, each with its own server, which the app starts and stops;
- a Dock icon, and folders opened from Finder with Open With or dropped on the icon;
- native menus, tabs across folders, recent items, and the last session restored.

## Opening Folders and Files

- **File > Open…** chooses one or more folders or files.
- **Finder’s Open With and the Dock icon** accept folders.
  A file opens through File > Open…, a drop on a window, or
  `open -a Metabrowser path/to/file`.
- **A file opens in its folder:** in the most specific open folder that contains it, or
  else in its own folder, as `metab FILE` serves the file’s folder.
  A symbolic link opens where it points.
- **A drop on a window:** a dropped folder opens as a folder of its own, and a dropped
  file opens as above.
  Dropped text and web links stay with the page.
- **A folder already open** brings its window forward instead of starting a second
  server.

Each folder has one server.
Closing a folder’s last window stops it, so reopening the folder starts a new one.
If a server stops answering or fails to start, the window says so and offers Retry,
Reveal Logs, and Runtime Settings….

Opening a folder in Desktop, Documents, Downloads, iCloud Drive, or on another volume
asks once for access, in Metabrowser’s name, because the app starts the server that
reads it.

## Windows and Tabs

- **Titles:** each window is titled with its folder’s short name, or its full name while
  another open folder has the same short name.
  The title’s tooltip gives the full name and whether the folder is local or a cached
  mirror; Command-click or right-click a local folder’s title for its path menu.
- **Tabs or windows:** Settings > Open folders in decides where a newly opened folder
  goes: as System Settings > Desktop & Dock > “Prefer tabs when opening documents” says
  (the default), as a tab of the front window, or in a window of its own.
  Window > Merge All Windows, Move Tab to New Window, and dragging a tab combine folders
  either way.
- **Links:** a link to the same server stays in the window, and Command-click opens it
  in a new tab of that folder’s window.
  A clicked link to another site opens in your default browser; a page cannot open one
  by itself.
- **Background tabs:** the tab each window shows keeps its page, and so do the three
  background tabs shown most recently.
  Any other background tab gives up its page to save memory and reloads it when shown,
  at the top of the page and without its Back and Forward history.

The menus add what a browser would: File > Restart Server, Open in Default Browser,
Reveal Server Log (each folder has its own log), and Print; View > Back, Forward, Reload
Page, and zoom, which the app remembers; Edit > Find; and Help > Metabrowser
Documentation and Reveal Logs Folder.
The mark at the title bar’s trailing end opens the project on GitHub.

## Recent Items

File > Open Recent and the Dock icon’s menu list what you opened lately, most recent
first: the folders you opened in the app, in either build of it, and the folders `metab`
served in Terminal. It is `metab`’s own list of
[recent targets](command-line.md#recent-targets), so `metab --recent` shows the same
entries, and a folder stays in it however many others you open, up to the list’s length.

- **A file** adds the folder it opened in.
- **A folder that is gone** stays listed, since the app never looks at a listed folder
  until you choose it; choosing it says the folder is gone, and removes it.
- **Clear Menu** empties the list, for `metab` too.
- **Only an open changes the order:** File > Open…, Open Recent, a drop, Open With, or
  `metab` in Terminal.
  The windows the app brings back at launch, and a server it restarts, leave the list as
  it was.
- **The Dock icon’s menu** lists the same items while the app is running, as the app
  last read them; it reads them again each time the menu is opened, for the next time.

## The Last Session

The app saves its folder windows as you work and once more at quit: each window’s frame,
tabs, and shown tab, and each tab’s folder and page.
It keeps the file in its folder under `~/Library/Application Support`.

At the next launch the windows and tabs come back, and only each window’s shown tab
loads its page. The servers start one at a time, the front tab’s first.

- **Privacy prompts:** a folder in a location macOS protects (Desktop, Documents,
  Downloads, iCloud Drive and other cloud storage, another volume, or a folder holding
  one, such as your home folder) starts only when you select its tab, so a launch raises
  no prompt for a folder nobody is looking at.
- **A moved folder:** a saved folder that now leads somewhere else through a symbolic
  link waits for its tab, then opens where the link leads.
- **The budget:** a launch rebuilds at most the front 20 windows and 50 tabs.
- **Turning it off:** clear Settings > “Reopen the last session’s folders when
  Metabrowser opens”. The session is still saved.

A restore brings back windows, tabs, frames, and pages, but not full screen, Spaces,
minimized windows, or each tab’s Back and Forward history.

## Choosing a metab

Metabrowser > Settings… shows the `metab` in use, its path, how the app found it, and
the `git` and `gh` it hands each server.
Its buttons are **Find Again**, **Choose metab…**, **Run Doctor** (`metab --doctor`),
and **Reveal Logs**; **Places looked** lists each place the last search tried and what
it found; and below them are Open folders in and the session setting.

At first launch, and again on Find Again, the app looks for `metab` in several places,
among them the one it used last, `METABROWSER_METAB`, and where uv and Homebrew install
commands; Places looked lists them in the order tried.
Your login shell’s `PATH` comes last: the login shell runs only when the other places
miss `metab`, `git`, or `gh`, and it runs your shell’s startup files in the app’s name,
which can take seconds.

- **The version:** the app runs `metab` 0.12.1 or later, and checks each candidate by
  running `metab --exit-on-eof --version`. A build from before `--exit-on-eof` is too
  old whatever its number says.
- **Trust:** the app runs a `metab` it found only if no other account can change it.
  A standard Homebrew prefix, writable by the `admin` group, fails that rule; Settings
  names each file it would not run, and why.
- **Choose metab…** runs the file you pick even so, such as a source checkout’s
  `.venv/bin/metab`. `open --env METABROWSER_METAB=/path/to/metab -a Metabrowser`
  instead names a `metab` for the search to try, under the same trust rule.
- **When it applies:** folders opened afterwards use the new choice; an open folder
  switches at its next Retry or File > Restart Server.
- **Upgrades:** when the `metab` file changes, the app checks it again, and if open
  folders run servers of the old version, it offers Restart Servers.
  An upgrade run in Terminal reaches those servers before the app notices, so restart
  them when it asks.

## What the App Shows Without a Usable metab

If the app finds no `metab` it can run, Settings opens and lists only the steps still
missing, each a command with a Copy button, and a link to the installation guide.
The screen names any older `metab` it found.

While no release meets the minimum ([Release Status](installation.md#release-status)),
the steps end in the source checkout the app was built from: install uv if it is missing
(`brew install uv` is offered when Homebrew is installed), run `make install` at the
root of that checkout, and use Choose metab… to pick its `.venv/bin/metab`.

Once a release meets it, the steps end in uv:

- without uv, uv’s installer and then `uv tool install metabrowser`, in a new Terminal
  window so that it finds uv;
- with uv, `uv tool install metabrowser`;
- with a `metab` in uv’s tool directory that does not run,
  `uv tool install --reinstall metabrowser`;
- with an older `metab`, an upgrade command that asks for the minimum or later rather
  than an exact version, so a later `uv tool upgrade` can move past it.

The app keeps watching, and when a usable `metab` appears, it opens the folders you
asked for by itself.
It never runs an installer.
It runs a uv only to ask where uv installs tools, and only a uv no other account can
change. If uv’s tool directory is not on your login shell’s `PATH`, the screen suggests
`uv tool update-shell` so that `metab` also runs in Terminal; the app does not need it.

## Moving the App to Applications

A copy opened from a disk image, or from the folder it was downloaded to, runs from a
read-only location and cannot be updated in place.
At launch such a copy shows “Move Metabrowser to Applications”: drag the app to
Applications in Finder and open it from there.
Its first button opens the Applications folder and, for a disk image, also shows the app
on the image; Continue goes on, and “Don’t remind me” stops the notice.
The app moves nothing itself.

## Known Limitations

- The tab bar has no new-tab button: a new folder tab comes from File > Open… with
  Settings set to tabs, or from Merge All Windows.
- A restarted server comes back on a new port, and local storage is per origin, so what
  a page kept there starts fresh, as with the CLI.
- The app does not pass state-location variables (`XDG_CACHE_HOME`,
  `METABROWSER_CACHE_DIR`, and the rest) to its servers, so they always use the default
  cache and configuration locations.
  A `metab` in Terminal that one of those variables points elsewhere keeps recent
  targets of its own, which File > Open Recent does not show.
- There is no updater and no URL scheme, and an agent cannot yet show you a page in the
  app; the
  [native macOS app plan](project/specs/active/plan-2026-11-10-native-macos-app.md) has
  what comes next.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
