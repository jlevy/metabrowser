# Keyboard Shortcuts

Every Metabrowser shortcut is a single key with no modifier, except Control-N and
Control-P on macOS and iOS, and Shift changes nothing.
A letter means the same thing wherever it works, `0` goes home, and the numbers `1` to
`9` reach the controls on the current screen in reading order.
Press `?` for Help, which lists the keys by what they do, and hold Shift to see each key
on the control it reaches now.
The strip at the foot of the navigation pane lists Shift first, as Reveal keys, then
`?`; in a narrow pane it keeps Shift and drops the others from the end, whose keys still
work.

## Letters and Numbers

| Key | Meaning | Works when |
| --- | --- | --- |
| `?` | Help | Always |
| `T` or `/` | Quick Search, the file finder | Always |
| `#` | Quick Search with the pull request prefix entered | A GitHub repository is shown |
| `0` | Home: the served folder’s home view, every tab at its first | Always |
| `\` | Hide or show the navigation pane | Always |
| `F` | The Files tab | Always |
| `P` | The Pulls tab | The Pulls tab is shown, for a GitHub repository |
| `H` | The Commits tab: commit History | The served folder is a Git repository’s root, or a repository opened by its URL |
| `J` or `K` | Down or up a row | A tree, Commits, Pulls, changed-file, or table row has focus |
| `Control-N` or `Control-P` | Next or previous item one level up: the pull requests of a stack | A pull request in a stack is open, outside text fields, on macOS and iOS |
| `U` | Up: the parent folder | A file, or a folder below the root, is shown |
| `W` | Open the branch or tag chooser below Files and Commits | A repository opened by its URL, or a folder that is a repository’s root, is shown |
| `V` | The rendered view: Document, Diagram, Preview, Table, Tree, Timeline, or Log | A file’s tab bar is shown |
| `A` | Table: a JSON or YAML list of records as a table | A JSON or YAML file is shown |
| `S` | The source: Source, or Raw JSON; a SQLite database’s Schema; or the Sessions list of an agent home | A file’s tab bar is shown, or a folder that is or holds a Claude Code or Codex home |
| `E` | Session, the session’s header and events | An agent log or a compressed Codex rollout is shown |
| `A` | Agents, the home of a Claude Code or Codex history | A folder that is or holds a Claude Code or Codex home is shown |
| `C` | Charts | An agent log is shown |
| `L` | Latency | An event log is shown |
| `B` | By kind | An event log is shown |
| `E` | Errors | An event log is shown |
| `I` | Info: how a SQLite database was read, its pages and log, and the SQLite library | A SQLite database or one of its tables is shown |
| `O` | Overview | A folder is shown |
| `M` | Treemap, from its map | A folder is shown |
| `C` | Conversation | A pull request page is shown |
| `D` | Docs: the changed documents, rendered | A pull request or stack page that changes a document is shown |
| `G` | Changes, from chan-*g*es | A pull request or stack page is shown |
| `R` | Guided Review, from guided P-*R*, a review | A pull request or stack page’s Guided Review tab is shown |
| `E` | Checks, from ch-*e*-cks | A pull request page is shown |
| `L` | Diff layout: Split or Unified | A diff with a layout control is shown |
| `N` | Switch between Diff and Excerpt (from curre*n*t) | A comparison toolbar is shown |
| `Y` | Diff File type: which types of changed files a diff shows | A diff of more than one file is shown |
| `1`–`9` | The numbered links and actions on this screen, in reading order | A numbered control is shown |

A letter that appears twice, such as `C`, belongs to two screens never shown together.

`0` does what a click on the folder’s name at the top of the navigation pane does: it
shows the folder as a fresh load shows it, with Files in front at the folder’s Overview,
every filter and Group by at its default, and every tab back at its first view.
What has been read, such as pull requests and history, stays in memory, so only the tree
and the folder’s view are read again.

Backslash does what a click on the chevron at the start of the main page’s foot does: it
hides the navigation pane, and the page slides over it to fill the window, or shows the
pane again. Shift-Backslash, which types `|` on a US keyboard, does the same.
Shortcuts use the character the key types.
On UK and German keyboards, the key in that position types `#`. Use the chevron on
layouts where Backslash needs Option or AltGr.
While the pane is hidden, the keys of its controls, such as `0`, `F`, and the filters’
numbers, do nothing until it is shown again.
With the pane hidden, a pull request page that waits on a fetch or a failed refresh
still offers Fetch or Retry on its status line, but its other refreshes, such as one for
a newer copy, wait for the navigation’s Refresh.

## Keys in a Menu

Opening a filter’s menu or a pull request’s stack menu, by a click, or by Enter, Space,
`↓`, or `↑` on its button, or a filter’s number, puts focus in it, so its keys work at
once: `↑`, `↓`, Home, End, Enter, and Escape.
While a menu is open and has focus, the letters of its rows come first: in Group by, `N`
chooses No grouping, `A` By age, and `T` By file type, where elsewhere `T` is Quick
Search. `/` still opens Quick Search there, and every letter means what the table says
again once the menu closes or focus leaves it.
Holding Shift shows each row’s letter, and Help lists them under Menus.

## Numbered Controls

Numbers are positional, so `1` reaches a different control on a different screen.
Each control is numbered only while it is shown:

| Screen | Numbered controls |
| --- | --- |
| Every tab | Refresh, the circular arrow at the top of the navigation pane, which is `1` under every tab: it refreshes everything the page shows, what is on screen first, and keeps its number while it waits |
| The Files tab | After Refresh: Group by, Modified within (Any age), and File type (Any type), whether the filter drawer is open or closed; a Git pin has Modified within, and Group by age, only where its Git can read file ages |
| The Pulls tab | After Refresh: Open, Closed, and All |
| A pull request page | The header’s links and actions, such as Browse code, the status line’s Retry or Fetch where it offers one, and Browse the checkout, in the order the header shows them; Retry keeps its number while it waits |
| A stack page | The status line’s Retry where it offers one, then Show the new comparison where it offers that |

The navigation pane’s numbers come first, so a pull request page’s numbers continue
after those of the tab beside it.
A tenth control gets no number.

Copy buttons, per-file controls such as a changed file’s View file or View on branch,
and controls that appear only on hover have no key; Tab and the pointer reach them.

## Lists and Search

In the file tree:

- Up and Down, or `K` and `J`, move a row and open it.
- Left collapses a folder or moves to its parent; Right expands a folder or moves to its
  first child.
- Home and End go to the first and last row.
- Enter or Space opens or closes a folder, or shows the next page of a long one.

In the Commits list, Up and Down or `K` and `J` move a row, and Enter or Space opens the
commit.

In the Pulls list, Up and Down or `K` and `J` move a row, a pull request’s three lines
being one, Enter opens the pull request, and Space shows or hides its changed files;
Right shows them or moves into them, and Left hides them.
Grouped by stack, a stack’s row opens nothing: Enter and Space open or close it, Right
opens it or goes to its first row, and Left closes it, or returns to it from its Stack
Overview row or from a pull request inside it, once that row’s files are closed.
An open stack’s first row, Stack Overview, above its pull requests, opens the stack’s
page: a move onto it opens it, as a move onto a pull request opens that, so `J` or Right
from the stack’s row opens it, and so does Enter.
Its other keys are a pull request’s row’s, for the whole stack’s changed files: Space
shows or hides them, Right shows them or moves into them, and Left hides them.

Press `#` to open Quick Search for pull requests.
The cursor starts after the prefix, ready for a number or title.
Up and Down move through the results, Enter opens one, and Escape closes Quick Search.
In Help, `?` or Escape closes it.

## Browser and App Keys

A key held with Command, Control, or Option belongs to the browser, and in the macOS app
to the app’s menus, except Control-N and Control-P on macOS and iOS, which no browser or
app menu uses there.
On Windows and Linux, where Control-N opens a window and Control-P prints, neither is
bound, and the stack menu on a pull request page walks the stack.
The other exception is Option-Tab inside a dialog or an open menu: the dialog or menu
keeps it, because Safari moves focus with Option-Tab.

In the macOS app, Command-Left Bracket and Command-Right Bracket go Back and Forward.
The bare `[` and `]` keys do the same while browsing a page.
Text fields and dialogs keep those keys.
Hold Shift to show the bracket hints on the available history buttons in the title bar.
In a browser, use its Back and Forward controls.

Command-R (Control-R or F5 elsewhere) always reloads, whatever has focus.
In the macOS app it is View > Reload Page, which also restarts a folder whose server
failed. The app’s other keys are the ones its menus show, which
[the app guide](macos-app.md) describes.

Command-P (Control-P elsewhere) prints the view shown, as the browser’s Print, and in
the macOS app it is File > Print.
A rendered Markdown document, opened as a file or as the README on a folder’s Overview,
also has a print button at its top right when the window is wide enough to show the
document as a card, and it prints the same way.

## For Plugin Authors

A plugin’s view tabs and controls take keys under the same rules.
[Keyboard shortcuts in the plugin guide](plugins.md#keyboard-shortcuts) has the API, and
the [design system](design-system.md#keyboard-shortcuts) has the rules for choosing a
letter.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
