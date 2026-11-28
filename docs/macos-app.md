# The macOS App

The Metabrowser app is an alpha preview built from source;
[Release Status](installation.md#release-status) says what that means today, and
[Installation](installation.md#the-macos-app) says how to build it.

The app is a native shell over `metab`. Everything inside a window is the page `metab`
serves, the same page a browser shows; View on GitHub shows the item’s page on
github.com in a popover over it.
What the app adds is what a browser tab cannot give:

- a window per folder or GitHub repository, each with its own server, which the app
  starts and stops;
- a Dock icon, and folders opened from Finder with Open With or dropped on the icon;
- native menus, recent items, and the last session restored;
- the item’s page on github.com a click away, with one GitHub sign-in for every window.

## Opening Folders and Files

- **File > Open Folder…** (Command-O) chooses one or more folders or files.
  It shows hidden folders and files, such as `~/.claude` with an agent’s logs;
  Command-Shift-Period hides them in the panel.
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
**File > Close Folder** closes the folder the front window shows in every window that
shows it; each of those windows shows the folder open in the background that you looked
at last, or closes if there is none.
While a dialog or panel is open on one of those windows, it does nothing.
If a server stops answering or fails to start, the window says so and offers Retry,
Reveal Server Log, and Runtime Settings….

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
running. [The command-line guide](command-line.md#presenting-a-target---present) has the
report, its codes, and `--dry-run`, which checks a target without sending it.

- **Which app:** `--present` asks LaunchServices, so it finds the app wherever macOS has
  registered it: an installed release first, then a development build, which is what
  every build from source is.
  `--app-bundle-id` or `METABROWSER_APP_BUNDLE_ID` names another.
- **Only the installed app:** `--present` sends only to a current build installed in the
  system’s or your own Applications folder, so install the app there and open it once.
  A build elsewhere, such as one left where it was built, is refused with
  `app_not_installed`, and an older build, or another app an override names, with
  `app_not_marked`, rather than send what it would drop or run.
  [The command-line guide](command-line.md#presenting-a-target---present) lists the
  checks and the developer setting that lifts the first.
- **A file:** a file named alone joins the most specific folder the app has open that
  holds it, and otherwise opens in its own folder.
  A file named with `--path` inside a folder opens in that folder, unless a folder
  inside it that holds the file is open already, where the file then shows.
- **A folder inside another:** the app opens each folder in a window of its own, so
  `--path` naming a folder is not sent to it; present that folder itself.
- **No app, or a browser by choice:** when no app takes the target, `--present` opens it
  in your browser instead, on a `metab` server it starts and leaves running, and reports
  the server’s address and process ID. Set `open_in` to `app` to send only to the app,
  or to `browser` to skip it, in `config.yml`, `METABROWSER_OPEN_IN`, or `--open-in`
  ([choosing the app or a browser](command-line.md#choosing-the-app-or-a-browser)).
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

- **File > Open URL…** takes a GitHub URL or a bare repository shortcut such as
  `jlevy/metabrowser`. When you press Open, the field shows the full URL. `owner/repo`
  expands to `https://github.com/owner/repo`, and `github.com/owner/repo`,
  `//github.com/owner/repo`, and `http://github.com/…` also open over HTTPS. Use the
  GitHub URL for a pull request, commit, file, or folder.
  A space or a letter outside ASCII in the path is sent encoded, as a browser sends it,
  so a file named `Design Notes.md` opens as it does with `metab URL`. Open checks the
  URL with `metab`. The panel shows progress until the repository window opens.
  If Metabrowser is still finding or checking its server runtime, the panel waits for
  it. If the URL check fails, no server runtime is available, or Metabrowser cannot open
  the repository window, the panel keeps your text and shows the reason under the field.
  Server startup progress and errors appear in the repository window.
- **Always the mirror:** a link opens Metabrowser’s own copy of the repository, its
  mirror in `metab`’s cache, never a checkout of it that you have open
  ([Open Modes](project/architecture/arch-open-modes.md)).
- **A window of its own:** the mirror opens in a new window, as every folder does, also
  while a window shows a checkout of the same repository, which keeps showing your
  working tree.
- **External links ask before a first clone.** A link sent by Terminal or another app
  asks before it clones a repository the cache does not hold.
  The dialog names the repository and says that Metabrowser will read it and its pull
  requests with your `gh` sign-in.
  Cancel is the default button.
  Other links go on opening while the question waits, and more links into the same
  repository wait for your one answer, which opens the newest.
  After Cancel, links into that repository sent in the same burst are not opened, and
  the app says how many; a link sent later asks again.
  A repository the cache holds opens without asking.
  Submitting Open URL… or choosing a repository from a native recent menu or the folder
  chooser gives permission for that open, so Metabrowser skips the clone dialog.
- **One window per repository:** a repository opens in one window, on its default
  branch, whatever link opened it, and every link into the repository opens in that
  window: a second pull request goes to its page in the same window, and a link to a
  branch, a commit, a folder, or a file goes to its page at the revision it names.
  Each link also refreshes the repository from GitHub, so what it shows is current.
  The window’s server keeps running, so this takes a moment, not a restart; when a link
  names another branch or commit than the window shows, the window switches to it, and
  its other windows offer to reload on it.
  A start under way, such as a first clone, finishes first, and the newest link sent
  meanwhile opens then.
  Without a window, a new one opens, and its server clones the repository, or uses the
  clone the cache has.
- **A branch or commit the copy lacks:** a link to a branch, tag, or commit pushed since
  the copy was last fetched waits for the refresh the link starts, then goes to the
  link’s page. If GitHub does not have it either, the window stays where it was and the
  app says so.
- **A first clone** of a large repository can take minutes.
  The window says it is starting meanwhile, with the clone’s progress under it, as
  `metab` reports it in Terminal: how far the clone has got, how fast, and for how long,
  then that it is done, and then that it is reading the pull request the link names.
  File > Reveal Server Log shows the whole account.
  The app waits for as long as the clone keeps reporting progress, up to `metab`’s own
  bound on a clone, and gives up on one that stops; the window then offers Retry.
  Folders you open meanwhile start at once; another repository waits for the clone, and
  its window says so.
- **When GitHub is the problem,** the window of a repository that could not be cloned
  says which problem it is.
  The repository was not found, which is also how GitHub answers when GitHub CLI (`gh`)
  is signed out, its account cannot read a private repository, or its sign-in lacks the
  `repo` scope; so a signed-out `gh` shows as not found, until Metabrowser checks the
  sign-in itself. Or the repository was not found and Metabrowser did not find GitHub CLI
  either, so it could offer GitHub no sign-in; or the connection to GitHub failed; or
  GitHub answered but is limiting requests, or answered with an error.
  It shows `metab`’s message and the commands that fix the problem or show what it is,
  each with Copy, and Copy Message copies all of it, to paste into a message or a note.
  When the repository was not found and GitHub CLI was, run the commands in Terminal and
  switch back: Metabrowser tries again by itself, as Retry does, and the window says so.
  Any other failure waits for Retry, since trying again on every switch could restart a
  long clone from the beginning or ask GitHub again while it asks for fewer requests.
  After installing GitHub CLI, choose Refresh in Settings > Runtime first, so that
  Metabrowser finds it, then Retry.
- **A link `metab` refuses**, such as an issues page, shows `metab`’s message, which
  says what to do. A link to another site, an `http` link, and a link with a user name, a
  password, or a port other than 443 show the app’s own message.
- **Many links at once** are read one at a time, a link sent again while it waits opens
  once, and what could not be opened is said in one message at the end, never over
  another message or question.
- **Not restored:** a repository’s window does not come back with the last session.

## Windows

- **Titles:** each window is titled with its folder’s short name, or its full name while
  another open folder has the same short name.
  The title’s tooltip gives the full name and whether the folder is a local folder, a
  local Git checkout, or a cloud mirror; Command-click or right-click a local folder’s
  title for its path menu.
- **Switching folders:** click a window’s title, marked by the small chevron after it,
  for the folder chooser.
  It lists the open folders, in the order you opened them, with a check mark beside the
  name of the window’s own, then the recent folders that are not open.
  Each row’s mark stands beside the name: a cloud for a GitHub repository, a folder with
  Git’s branch for a Git checkout, and a folder with a dot for any other folder, the
  same marks as at the top of the page’s navigation column, and the row’s location, or
  “In another window”, is the line below the name; a location too long for that line is
  cut in the middle, and its tooltip gives all of it.
  Choosing a folder or repository brings its window forward or opens a separate window
  for it. A folder open in the background keeps its page and server when it gets a window
  of its own. **Close Background Folders** at the foot of the chooser closes every folder
  no window shows. Dragging the title still moves the window; a double-click on it opens
  the chooser too, where the rest of the title bar zooms the window.
- **Switching by keyboard:** View > Switch Folder… (Shift-Command-O) opens a panel over
  the window that lists the same folders, the one you looked at last first, so
  Shift-Command-O then Return goes back to it.
  Type to filter by name or path, Return to go to the selected folder (in this window,
  or by bringing forward the window that shows it), Option-Return to open it in a new
  window, and Escape to close the panel.
  Command-Delete clears what you typed; with nothing typed, it closes the selected open
  folder.
- **A window per folder:** every folder opens in a window of its own, from File > Open
  Folder…, Open URL…, Open Recent, the Dock, Finder, `metab --present`, or the folder
  chooser, and a window never becomes a tab of another.
  Window > Merge All Windows and the tab bar are not offered, and System Settings >
  Desktop & Dock > “Prefer tabs when opening documents” does not apply.
  A folder already open brings its window forward instead.
- **Links:** a link to the same server stays in the window, and Command-click opens it
  in a new window of the same folder, which shares its server.
  A clicked link to another site opens in your default browser; a page cannot open one
  by itself. The page’s View on GitHub button is the exception: it opens the item’s page
  on github.com in a popover ([View on GitHub](#view-on-github)).
- **Open:** a PDF’s view has Open, which opens the PDF in the app your Mac uses for
  PDFs, Preview unless you chose another; Download saves a copy instead.
  In a folder, Open opens the file itself.
  For a pinned revision or a GitHub repository, which have no file on your Mac, it opens
  a read-only copy that Metabrowser downloads to its caches folder and removes at a
  later launch; a copy of a file without an extension takes the one its type has, so a
  PDF named `untitled` opens as `untitled.pdf`. Open opens only PDFs, images, audio, and
  video, never a script, an app, or an installer.
  When no app on your Mac opens that kind of file, Open saves a copy in Downloads
  instead, under a new name if the name is taken, and offers Show in Finder; the first
  time, macOS asks whether Metabrowser may use Downloads.
- **Folders in the background:** each window keeps its page, minimized or not, and so do
  the three background folders shown most recently.
  Any other folder open in the background gives up its page to save memory and reloads
  it when a window shows it again, at the top of the page and without its Back and
  Forward history.

The menus add what a browser would: File > Restart Server, Open in Default Browser,
Reveal Server Log (each folder has its own log), and Print; View > Back, Forward, Reload
Page, and zoom, which the app remembers; Edit > Find; and Help > Metabrowser
Documentation, Check Setup…, Reveal Logs Folder, and Open Event Log, which opens
Metabrowser’s own [event log](realtime-debugging.md#browsing-the-log), the record of
what the servers it runs did and how long each took, at its newest segment in a window
on the log’s own folder, which Open Recent does not list.
The mark at the title bar’s trailing end opens the project on GitHub.

Back and Forward sit to the right of the project chooser and move through that project’s
page history. Hold either button or secondary-click it to open a menu of pages in that
direction, nearest first.
Choose a page to jump directly to it.

The address field shows the current page on the local Metabrowser server.
Click the address to select it or open it in your default browser.
The link icon copies the address to the clipboard.

Edit > Find (Command-F) opens a find bar above the page.
It searches as a browser’s find does: the whole page, the navigation pane included,
without regard to case, wrapping at either end, and it searches the page as it is now,
after you open another file in place.
Typing searches as you go; Return or Command-G finds the next match, Shift-Return or
Shift-Command-G the previous one; Command-E makes the selected text the search string;
and Escape or Done closes the bar.
The search string is the one other apps’ Find shares.

## View on GitHub

A page whose file, folder, pull request, or commit has a page on github.com shows a View
on GitHub button in its upper right ([Browsing Files](browsing-files.md)). In the app,
clicking it opens that page on github.com in a popover below the button, over most of
the window, without leaving Metabrowser’s page.

- **Closing it:** Escape, Command-W, or a click outside the popover closes it.
  Opened again soon after for the same item, it is as you left it, with its Back and
  Forward history; after it has stayed closed a while, it loads the page again, unless
  you had typed a comment or other text there and not sent it, which it keeps.
  A page that did not load, offline say, loads again when you open the popover or press
  Command-R.
- **In the popover:** a header holds Back and Forward, the github.com location the
  popover shows, Copy Link, and Open in Browser, which opens that page in your default
  browser and closes the popover.
  While the popover has the keyboard, View > Back, Forward, Reload Page, and zoom act on
  it, and so does File > Open in Default Browser; File > Print and Edit > Find are off.
  Its zoom is its own: it starts at actual size and is not remembered.
- **The button’s menu:** Copy Link copies the github.com address, and Open in Browser
  opens it in your default browser instead of the popover.
  A Command-click on the button opens your browser too.
- **Files and dialogs:** a file panel GitHub asks for, such as “click to add files” on a
  comment box, and a question it asks, such as whether to discard an edit, open over the
  popover, which stays open behind them.
- **Links in the popover:** pages on github.com and on GitHub’s content and asset sites
  (githubusercontent.com and githubassets.com) stay in the popover.
  A link to any other site, and a download, opens in your default browser.
  A file you drop on the popover, such as a screenshot on a comment box, goes to
  github.com.
- **Only the button:** a GitHub link you send to the app, with File > Open URL…,
  `metab URL --present`, or `open -b`, still opens Metabrowser’s own view of it
  ([Opening GitHub Links](#opening-github-links)), and a link to github.com anywhere
  else in a page opens in your default browser.

### Signing In to GitHub

Sign in to github.com once, in any window’s popover, and you stay signed in in every
window, and after you quit and reopen the app.
The popover keeps what github.com stores, its sign-in cookies, cache, and other site
data, in one store of the app’s own, which every site the app shows in its own web views
shares, as a browser profile does; macOS keeps it under `~/Library/WebKit` in the app’s
folder. It is apart from your browser, from Metabrowser’s own pages and settings, and
from your `gh` sign-in, which is what Metabrowser reads repositories and pull requests
with. A development build keeps a store of its own.

- **Who can use it:** as with a browser, anyone using your Mac account can open the app
  and act as you on github.com.
- **Signing out:** sign out on github.com in the popover, or choose Metabrowser > Clear
  Website Data…, pick `github.com` or All Websites, and Clear.
  That removes everything the sites you picked stored in the app, signs you out of them
  in every window, and reloads each popover showing one of them.
  It leaves your `gh` sign-in, your browser, and Metabrowser’s settings as they were.
- **Ways to sign in:** a password, with GitHub’s two-factor code, signs in within the
  popover. A sign-in that goes through another site, such as an organization’s single
  sign-on, opens that site in your default browser, so it signs you in there and not in
  the app.

## Recent Items

File > Open Recent, the Dock icon’s menu, and the folder chooser’s Recent section list
what you opened lately, most recent first: the folders and GitHub repositories you
opened in the app, in either build of it, and those `metab` served in Terminal.
It is `metab`’s own list of [recent targets](command-line.md#recent-targets), so
`metab --recent` shows the same entries, and a folder stays in it however many others
you open, up to the list’s length.

- **A file** adds the folder it opened in.
- **A GitHub link** adds its repository, which reopens on its default branch.
- **A folder that is gone** stays listed, since the app never looks at a listed folder
  until you choose it; choosing it says the folder is gone, and removes it.
- **Clear Menu** empties the list, for `metab` too.
- **Only an open changes the order:** File > Open Folder…, Open URL…, Open Recent, a
  drop, Open With, a GitHub link, a folder chosen in the folder chooser or Switch
  Folder…, or `metab` in Terminal.
  Each open moves its folder to the top once, as it opens, even if its server then
  fails. The windows the app brings back at launch, and a server it restarts, leave the
  list as it was.
- **Only your opens are listed.** A `metab` that an agent, a test, or a tool runs has no
  terminal, so the folders it serves stay out of the list.
  A folder an agent shows you with `metab --present` is listed, since the app cannot
  tell it from one you opened.
  A development build that `make macos-run` starts lists nothing it opens, since agents
  start the app that way for their checks.
- **The Dock icon’s menu** lists the same items while the app is running, as the app
  last read them; it reads them again each time the menu is opened, for the next time.

## The Last Session

The app saves its folder windows as you work and once more at quit: each window’s frame,
folder, and page. It keeps the file in its folder under `~/Library/Application Support`.

At the next launch the windows come back.
The servers start one at a time, the front window’s first.

- **From an earlier version:** a window that an earlier version saved with several
  folders in its tabs comes back as a window per folder.
  The folder it showed comes back at its frame and in front, and loads its page; each of
  the others loads its page when you bring its window forward.
- **Privacy prompts:** a folder in a location macOS protects (Desktop, Documents,
  Downloads, iCloud Drive and other cloud storage, another volume, or a folder holding
  one, such as your home folder) starts only when you bring its window forward, so a
  launch raises no prompt for a folder nobody is looking at.
- **A moved folder:** a saved folder that now leads somewhere else through a symbolic
  link waits until you bring its window forward, then opens where the link leads.
- **Folders in the background** come back in the background, and each starts its server
  when a window shows it.
  If no window was open, the one you looked at last opens in a window of its own.
- **The budget:** a launch rebuilds at most the front 20 windows and 50 pages, a folder
  in the background counting as one.
- **Turning it off:** clear Settings > General > “Reopen the last session’s folders when
  Metabrowser opens”. The session is still saved.

A restore brings back windows, frames, and pages, but not full screen, Spaces, minimized
windows, or each window’s Back and Forward history.

## Settings

**Metabrowser → Settings…** has four tabs along its toolbar, and opens at the one it
showed last, General at first.
Each tab sizes the window to fit, keeping its top edge in place.

- **General:** whether the [last session](#the-last-session) reopens.
- **Runtime:** the selected `metab`, its path, how the app found it, and the `git` and
  `gh` it hands each server, with **Refresh** and **Choose metab…**
  ([Choosing a metab](#choosing-a-metab)). **Places looked** lists the last runtime
  search, scrolling within the tab when it is long, and **Reveal Logs Folder** shows the
  app’s logs in Finder, as Help > Reveal Logs Folder does.
- **Plugins:** the plugins a new server started with this runtime discovers, each with
  its name, ID, version, source, and the plugins it requires, then any discovery errors.
  The app runs [the CLI’s plugin inventory](plugins.md#inspecting-plugins) with the same
  environment it uses to start its servers, the first time the tab shows a runtime and
  again on **Refresh**, so the list is the inventory `metab --plugins` reports for that
  runtime.
- **Check Setup:** the [setup report](#checking-the-setup).

**Metabrowser → About Metabrowser** shows the app build and links to the
[Metabrowser GitHub repository](https://github.com/jlevy/metabrowser).

## Choosing a metab

At first launch, and again on Settings > Runtime > Refresh, the app looks for `metab` in
several places, among them the one it used last, `METABROWSER_METAB`, and where uv and
Homebrew install commands; Places looked lists them in the order tried.
Your login shell’s `PATH` comes last: the login shell runs only when the other places
miss `metab`, `git`, or `gh`, and it runs your shell’s startup files in the app’s name,
which can take seconds.

- **The version:** the app runs `metab` 0.13.0 or later, and checks each candidate by
  running `metab --exit-on-eof --present --recent --version`. A build from before any of
  those flags is too old whatever its number says.
- **Trust:** the app runs a `metab` it found only if no other account can change it.
  A standard Homebrew prefix, writable by the `admin` group, fails that rule; Settings >
  Runtime names each file it would not run, and why.
- **Choose metab…** runs the file you pick even so, such as a source checkout’s
  `.venv/bin/metab`. `open --env METABROWSER_METAB=/path/to/metab -a Metabrowser`
  instead names a `metab` for the search to try, under the same trust rule.
- **When it applies:** folders opened afterwards use the new choice; an open folder
  switches at its next Retry or File > Restart Server.
- **Upgrades:** when the `metab` file changes, the app checks it again, and if open
  folders run servers of the old version, it offers Restart Servers.
  An upgrade run in Terminal reaches those servers before the app notices, so restart
  them when it asks.

## Checking the Setup

Help > Check Setup… opens Settings at its Check Setup tab, which runs
`metab --doctor --json` with the `metab`, `git`, and `gh` the app hands its servers each
time it comes on screen.
A line at the top says whether `metab` can serve a folder with this setup, and names
each check that needs a look.
Below it is the whole report as plain text, headed by the app’s build and the `metab` it
ran: one block each for the plugins, opening from a terminal, `metab`, Git, the
configuration directory, the cache directory, the event log, and GitHub CLI, in the form
`metab --doctor` prints, a line with the check’s name, state, and summary, then what it
found, indented. A long line wraps under its own indent, and the report scrolls.
Select any part of it and copy it with Command-C. **Setup Help** opens the
[README’s installation and troubleshooting section](https://github.com/jlevy/metabrowser#installation).
[Diagnostics](command-line.md#diagnostics-and-plugins) says what each check covers.
The `metab` check compares with the oldest `metab` this build of the app runs.
The Git check names that `git`, its version, and whether it reads file ages on a Git
revision; a Git too old for them is a warning that says which release it needs.

- **Refresh** runs it again, as after following a step or choosing a `metab` in the
  Runtime tab. A selection in the report stays on its text, and the report stays where it
  was scrolled.
- **Copy Report** copies the whole report, for a bug report.
- **A `metab` built before the setup checks** shows its problems as it words them, and
  says the checks are missing.
  Use **Setup Help** to choose a newer runtime.
- **A check this app cannot read,** such as one from a later `metab`, says so, and the
  other checks still show.
- **No report:** when `metab` cannot run, does not finish within a minute, or prints
  something other than a report, the tab says so and shows what it printed.

The check changes nothing, and only GitHub CLI’s sign-in check reaches the network.

## What the App Shows Without a Usable metab

If discovery finds no usable `metab`, Settings > Runtime shows the required version and
why it skipped or rejected any runtimes it found.
**Installation and troubleshooting on GitHub** opens the
[README](https://github.com/jlevy/metabrowser#installation) for installing or updating
the CLI and for preview builds whose runtime is pending on PyPI. After setup, use
**Refresh** or **Choose metab…** to select your runtime.

The app keeps watching, and when a usable `metab` appears, it opens the folders you
asked for by itself.
It only runs uv to locate the tool directory, using an executable that passes its trust
check.

## Moving the App to Applications

A copy opened from a disk image, or from the folder it was downloaded to, runs from a
read-only location and cannot be updated in place.
At launch such a copy shows “Move Metabrowser to Applications”: drag the app to
Applications in Finder and open it from there.
Its first button opens the Applications folder and, for a disk image, also shows the app
on the image; Continue goes on, and “Don’t remind me” stops the notice.
The app moves nothing itself.

## Known Limitations

- The View on GitHub popover cannot be resized: it takes most of the window each time it
  opens, so a larger window gives a larger popover.
- Text typed in the View on GitHub popover and not sent is lost when its window or its
  folder closes, when its window switches to another folder while another window shows
  this one, or when its folder, open in the background, gives up its page to save
  memory.
- A restarted server comes back on a new port, and local storage is per origin, so what
  a page kept there starts fresh, as with the CLI.
- Open on a pinned revision or a GitHub repository opens a read-only copy: to change the
  file, open it from a folder on your Mac.
- The app does not pass the cache’s location variables (`XDG_CACHE_HOME`,
  `METABROWSER_CACHE_DIR`) or `XDG_CONFIG_HOME` to its servers, so they always use the
  default cache. It does pass on a `METABROWSER_CONFIG_DIR` it was launched with, as in
  `open --env METABROWSER_CONFIG_DIR=/path/to/config -a Metabrowser`, so that launch
  keeps its recent targets and `config.yml` there.
  Launched from Finder or the Dock, it uses the default configuration directory, unless
  launchd’s own environment sets one (`launchctl setenv`); a terminal’s `export` does
  not reach it. A `metab` in Terminal that `METABROWSER_CONFIG_DIR` or `XDG_CONFIG_HOME`
  points elsewhere keeps recent targets of its own, which File > Open Recent does not
  show.
- A repository that another `metab`, in Terminal say, is cloning at the same moment does
  not open until that clone ends: the window’s start is given up on meanwhile, and Retry
  then opens it from the cache.
  A repository opened while another repository’s first clone runs starts once that clone
  ends, and so do a link into a repository that is already open and File > Restart
  Server in one of its windows: its other windows keep working meanwhile, and the window
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
