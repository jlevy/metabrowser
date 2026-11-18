# The macOS App

The Metabrowser app is an alpha preview built from source;
[Release Status](installation.md#release-status) says what that means today, and
[Installation](installation.md#the-macos-app) says how to build it.

The app is a native shell over `metab`. Everything inside a window is the page `metab`
serves, the same page a browser shows, or, when you choose its GitHub view, the same
item’s page on github.com.
What the app adds is what a browser tab cannot give:

- a window per folder or GitHub repository, each with its own server, which the app
  starts and stops;
- a Dock icon, and folders opened from Finder with Open With or dropped on the icon;
- native menus, tabs across folders, recent items, and the last session restored;
- the item’s page on github.com in the window, beside Metabrowser’s view of it, with one
  GitHub sign-in for every window.

## Opening Folders and Files

- **File > Open Folder…** (Command-O) chooses one or more folders or files.
- **Finder’s Open With and the Dock icon** accept folders.
  A file opens through File > Open Folder…, a drop on a window, or
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

## Opening From a Terminal or an Agent

```shell
metab ./notes --present
metab ./notes/report.md --present
metab https://github.com/owner/repo/pull/123 --present
```

`metab ROOT --present` hands a folder, a file, or a GitHub URL to the app and says what
it sent; the app opens it as it opens a folder from Finder, and starts if it is not
running. [The command-line guide](command-line.md#handing-a-target-to-the-app---present)
has the report, its codes, and `--dry-run`, which checks a target without sending it.

- **Which app:** `--present` asks LaunchServices, so it finds the app wherever macOS has
  registered it: an installed release first, then a development build, which is what
  every build from source is.
  `--app-bundle-id` or `METABROWSER_APP_BUNDLE_ID` names another.
- **Only the installed app:** `--present` sends only to a current build installed in the
  system’s or your own Applications folder, so install the app there and open it once.
  A build elsewhere, such as one left where it was built, is refused with
  `app_not_installed`, and an older build, or another app an override names, with
  `app_not_marked`, rather than send what it would drop or run.
  [The command-line guide](command-line.md#handing-a-target-to-the-app---present) lists
  the checks and the developer setting that lifts the first.
- **A file:** a file named alone joins the most specific folder the app has open that
  holds it, and otherwise opens in its own folder.
  A file named with `--path` inside a folder opens in that folder, unless a folder
  inside it that holds the file is open already, where the file then shows.
- **A folder inside another:** the app opens each folder in a window of its own, so
  `--path` naming a folder is not sent; present that folder itself.
- **No confirmation yet:** the app does not answer, so `--present` reports what
  LaunchServices accepted, never that a window shows it.
- **In an agent’s sandbox,** LaunchServices may not answer; the report says
  `lookup_failed` or `open_failed`, with its own exit status, rather than that no app is
  installed.
  [Working with agents](working-with-agents.md#let-an-agent-reach-the-app-from-a-sandbox)
  has the settings that let an agent run `--present` outside its sandbox, and the
  `metabrowser` skill uses `--present` to hand you pages.

## Opening GitHub Links

The app opens the GitHub links `metab URL` opens in a browser: a repository, a pull
request and its tabs, a commit, and a file or folder at a branch, tag, or commit.
File > Open URL… (Command-L) opens one you paste or type, `metab URL --present` sends
one to the app, and so does `open -b io.github.jlevy.metabrowser URL`
(`io.github.jlevy.metabrowser.dev` for a development build).
`metab` reads each link first, and the app shows what `metab` makes of it.

- **File > Open URL…** takes the full URL, starting with `https://github.com/`; a
  shorthand such as `owner/repo` is not opened.
  A space or a letter outside ASCII in the path is sent encoded, as a browser sends it,
  so a file named `Design Notes.md` opens as it does with `metab URL`. Open checks the
  URL with `metab`, and a URL it accepts opens as a sent link does, below.
  A URL it does not open keeps the panel open with the reason under the field: the app’s
  own for anything but an `https` URL on GitHub, and `metab`’s for a GitHub page it does
  not open, such as an issues page.
  One exception: while Metabrowser is still finding its `metab`, or checking it again
  after it changed, the panel closes at once, the URL is checked once `metab` is ready,
  and a URL it does not open is reported in an alert.
- **Always the mirror:** a link opens Metabrowser’s own copy of the repository, its
  mirror in `metab`’s cache, never a checkout of it that you have open
  ([Open Modes](project/architecture/arch-open-modes.md)).
- **Asked once before a clone:** a link to a repository the cache does not hold yet asks
  first, naming the repository: opening it clones the repository into the cache and
  reads it, and its pull requests, with your `gh` sign-in.
  Cancel is the default button.
  Other links go on opening while the question waits, and more links into the same
  repository wait for your one answer, which opens the newest.
  After Cancel, links into that repository sent in the same burst are not opened, and
  the app says how many; a link sent later asks again.
  A repository the cache holds opens without asking.
- **One window per repository:** a link into a repository that has a window brings that
  window forward, on the branch, commit, or pull request the link names and at its page.
  Its server starts again on the link, which takes a few seconds, its other tabs reload
  on that revision, and what pages kept in local storage starts fresh, since the server
  comes back on a new port.
  A start under way, such as a first clone or a File > Restart Server, finishes first,
  and sending the same link again meanwhile starts nothing more: the window still comes
  to the link’s page once that start ends.
  Without a window, a new one opens, and its server clones the repository, or uses the
  clone the cache has.
- **A branch or commit the copy lacks:** a link to a branch, tag, or commit pushed since
  the copy was last fetched opens the default branch while `metab` fetches it, then goes
  to the link’s page. If GitHub does not have it either, or the fetch fails, the windows
  stay on the default branch and the app says so.
- **A first clone** of a large repository can take minutes.
  The window says it is starting meanwhile, and File > Reveal Server Log shows the
  clone’s progress. The app waits for as long as the clone keeps reporting progress, up
  to `metab`’s own bound on a clone, and gives up on one that stops; the window then
  offers Retry. Folders you open meanwhile start at once; another repository waits for
  the clone, and its window says so.
- **A link `metab` refuses**, such as an issues page, shows `metab`’s message, which
  says what to do. A private repository that your `gh` sign-in cannot read opens a window
  whose server fails, with its message and Retry.
  A link to another site, an `http` link, and a link with a user name, a password, or a
  port other than 443 show the app’s own message.
- **Many links at once** are read one at a time, a link sent again while it waits opens
  once, and what could not be opened is said in one message at the end, never over
  another message or question.
- **Not restored:** a repository’s window does not come back with the last session.

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
  by itself. The view header’s GitHub mark is the exception: it shows the item’s page on
  github.com in the window ([The GitHub View](#the-github-view)).
- **Background tabs:** the tab each window shows keeps its page, and so do the three
  background tabs shown most recently.
  Any other background tab gives up its page to save memory and reloads it when shown,
  at the top of the page and without its Back and Forward history.

The menus add what a browser would: File > Restart Server, Open in Default Browser
(Shift-Command-O), Reveal Server Log (each folder has its own log), and Print; View >
Back, Forward, Reload Page, Show GitHub View (Option-Command-G), and zoom, which the app
remembers; Edit > Find; and Help > Metabrowser Documentation and Reveal Logs Folder.
The mark at the title bar’s trailing end opens the project on GitHub.

## The GitHub View

On a page of a repository on github.com, the view header’s upper right holds a toggle of
two marks, Metabrowser’s and GitHub’s ([Browsing Files](browsing-files.md)). In the app,
choosing GitHub shows the same file or folder on github.com in the window itself, in
place of the page.

- **Back to Metabrowser:** a thin bar above the github.com page holds the same toggle,
  with GitHub pressed, where the page’s own toggle sits.
  Choose Metabrowser there, or View > Show Metabrowser View (Option-Command-G), and the
  window shows its page again as you left it: the same page, scroll position, and state.
- **Back to GitHub:** choose GitHub again, from the page or with View > Show GitHub
  View, and the github.com page is as you left it too, with its Back and Forward
  history. From another file or folder, the GitHub view goes to that item’s page.
- **The bar** names the github.com location the view shows, so you can see which site
  you are on, such as when you sign in.
- **The menus act on the view shown:** View > Back, Forward, Reload Page, and zoom, Edit
  \> Find, File > Print, and File > Open in Default Browser, which opens the github.com
  page in your browser.
- **Links in the GitHub view:** pages on github.com and on GitHub’s content and asset
  sites (githubusercontent.com and githubassets.com) stay in the view.
  A link to any other site opens in your default browser, and so does a Command-click on
  a GitHub link.
- **Only the toggle:** a GitHub link you send to the app, with File > Open URL…,
  `metab URL --present`, or `open -b`, still opens Metabrowser’s own view of it
  ([Opening GitHub Links](#opening-github-links)), and a link to github.com anywhere
  else in a page still opens in your default browser.
  A Command-click on the toggle’s GitHub mark opens your browser too.
- **The Metabrowser view first:** a file or link sent to a window, a reopened session,
  and a tab that gave up its page to save memory, which gives up its GitHub view with
  it, show the Metabrowser view.

### Signing In to GitHub

Sign in to github.com once, in any GitHub view, and you stay signed in in every window
and tab, and after you quit and reopen the app.
Every GitHub view keeps what github.com stores, its sign-in cookies, cache, and other
site data, in one store of the app’s own, which macOS keeps under `~/Library/WebKit` in
the app’s folder. It is apart from your browser, from Metabrowser’s own pages and
settings, and from your `gh` sign-in, which is what Metabrowser reads repositories and
pull requests with. A development build keeps a store of its own.

- **Who can use it:** as with a browser, anyone using your Mac account can open the app
  and act as you on github.com.
- **Signing out:** sign out on github.com in the GitHub view, or choose Metabrowser >
  Clear GitHub Data…, which removes everything github.com stored in the app, signs you
  out in every window, and reloads each GitHub view.
  It leaves your `gh` sign-in, your browser, and Metabrowser’s settings as they were.
- **Ways to sign in:** a password, with GitHub’s two-factor code, signs in within the
  view. A sign-in that goes through another site, such as an organization’s single
  sign-on, opens that site in your default browser, so it signs you in there and not in
  the app.

## Recent Items

File > Open Recent and the Dock icon’s menu list what you opened lately, most recent
first: the folders and GitHub repositories you opened in the app, in either build of it,
and those `metab` served in Terminal.
It is `metab`’s own list of [recent targets](command-line.md#recent-targets), so
`metab --recent` shows the same entries, and a folder stays in it however many others
you open, up to the list’s length.

- **A file** adds the folder it opened in.
- **A GitHub link** adds its repository, which reopens on its default branch.
- **A folder that is gone** stays listed, since the app never looks at a listed folder
  until you choose it; choosing it says the folder is gone, and removes it.
- **Clear Menu** empties the list, for `metab` too.
- **Only an open changes the order:** File > Open Folder…, Open URL…, Open Recent, a
  drop, Open With, a GitHub link, or `metab` in Terminal.
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
  running `metab --exit-on-eof --present --recent --version`. A build from before any of
  those flags is too old whatever its number says.
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

- The tab bar has no new-tab button: a new tab comes from File > Open Folder… or Open
  URL… with Settings set to tabs, or from Merge All Windows.
- A restarted server comes back on a new port, and local storage is per origin, so what
  a page kept there starts fresh, as with the CLI.
- The app does not pass state-location variables (`XDG_CACHE_HOME`,
  `METABROWSER_CACHE_DIR`, and the rest) to its servers, so they always use the default
  cache and configuration locations.
  A `metab` in Terminal that one of those variables points elsewhere keeps recent
  targets of its own, which File > Open Recent does not show.
- A repository that another `metab`, in Terminal say, is cloning at the same moment does
  not open until that clone ends: the window’s start is given up on meanwhile, and Retry
  then opens it from the cache.
  A repository opened while another repository’s first clone runs starts once that clone
  ends, and so do a link into a repository that is already open and File > Restart
  Server in one of its windows: its other tabs keep working meanwhile, and the window
  the link brought forward, or the one you chose Restart Server in, says it waits.
- A folder opens as the folder named, even inside a Git repository, and File > Open URL…
  opens the repository’s mirror without offering a checkout of it that you have open.
  Opening the repository’s root instead, and that offer, are planned in
  [Open Modes](project/architecture/arch-open-modes.md#the-file-menu).
- There is no updater and no URL scheme, and an agent can hand the app a target with
  [`--present`](#opening-from-a-terminal-or-an-agent) but cannot yet learn which window
  shows it or move a page that is already open; the
  [native macOS app plan](project/specs/active/plan-2026-11-10-native-macos-app.md) has
  what comes next.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
