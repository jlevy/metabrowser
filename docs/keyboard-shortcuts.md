# Keyboard Shortcuts

Every Metabrowser shortcut is a single key with no modifier, except Control-N and
Control-P on macOS and iOS, and Shift changes nothing.
A letter means the same thing wherever it works, `0` goes home, and the numbers `1` to
`9` reach the controls on the current screen in reading order.
Press `?` for Help, which lists the keys by what they do, and hold Shift to see each key
on the control it reaches now.

## Letters and Numbers

| Key | Meaning | Works when |
| --- | --- | --- |
| `?` | Help | Always |
| `T` or `/` | Quick Search, the file finder | Always |
| `0` | Home: the served folder’s home view, every tab at its first | Always |
| `F` | The Files tab | Always |
| `P` | The Pulls tab | The Pulls tab is shown, for a GitHub repository |
| `H` | The Commits tab: commit History | The served folder is a Git repository’s root, or a repository opened by its URL |
| `J` or `K` | Down or up a row | A tree, Commits, Pulls, or changed-file row has focus |
| `Control-N` or `Control-P` | Next or previous item one level up: the pull requests of a stack | A pull request in a stack is open, outside text fields, on macOS and iOS |
| `U` | Up: the parent folder | A file, or a folder below the root, is shown |
| `W` | The branch or tag switcher | A pinned revision of a cached repository is shown |
| `V` | The rendered view: Document, Preview, Tree, or Log | A file’s tab bar is shown |
| `S` | The source: Source, or Raw JSON | A file’s tab bar is shown |
| `C` | Charts | An agent log is shown |
| `O` | Overview | A folder is shown |
| `M` | Treemap, from its map | A folder is shown |
| `C` | Conversation | A pull request page is shown |
| `G` | Changes, from chan-*g*es | A pull request page is shown |
| `E` | Checks, from ch-*e*-cks | A pull request page is shown |
| `L` | Diff layout: Split or Unified | A diff with a layout control is shown |
| `1`–`9` | The numbered links and actions on this screen, in reading order | A numbered control is shown |

A letter that appears twice, such as `C`, belongs to two screens never shown together.

`0` does what a click on the folder’s name at the top of the navigation pane does: it
shows the folder as a fresh load shows it, with Files in front at the folder’s Overview,
every filter and Group by at its default, and every tab back at its first view.
What has been read, such as pull requests and history, stays in memory, so only the tree
and the folder’s view are read again.

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
| The Files tab | Group by, Modified within (Any age), and File type (Any type), whether the filter drawer is open or closed; a Git pin has no Modified within |
| The Pulls tab | Open, Closed, and All, then Reload, which keeps its number while it waits |
| A pull request page | The header’s links and actions, such as View on GitHub, Browse code, and Refresh, in the order the header shows them |

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

In the Pulls list, Up and Down or `K` and `J` move a row, Enter opens the pull request,
and Space shows or hides its changed files; Right shows them and Left hides them.
Grouped by stack, a stack’s row opens nothing: Enter and Space open or close it, Right
opens it or goes to its first pull request, and Left closes it or returns to it from a
pull request inside it whose files are closed.

In Quick Search, Up and Down move through the results, Enter opens one, and Escape
closes it. In Help, `?` or Escape closes it.

## Browser and App Keys

A key held with Command, Control, or Option belongs to the browser, and in the macOS app
to the app’s menus, except Control-N and Control-P on macOS and iOS, which no browser or
app menu uses there.
On Windows and Linux, where Control-N opens a window and Control-P prints, neither is
bound, and the stack menu on a pull request page walks the stack.
The other exception is Option-Tab inside a dialog or an open menu: the dialog or menu
keeps it, because Safari moves focus with Option-Tab.

Command-R (Control-R or F5 elsewhere) always reloads, whatever has focus.
In the macOS app it is View > Reload Page, which also restarts a folder whose server
failed. The app’s other keys are the ones its menus show, which
[the app guide](macos-app.md) describes.

Command-P (Control-P elsewhere) prints the view shown, as the browser’s Print, and in
the macOS app it is File > Print.
A rendered Markdown document, opened as a file or as the README on a folder’s Overview,
also has a print button at its top right, which prints the same way.

## For Plugin Authors

A plugin’s view tabs and controls take keys under the same rules.
[Keyboard shortcuts in the plugin guide](plugins.md#keyboard-shortcuts) has the API, and
the [design system](design-system.md#keyboard-shortcuts) has the rules for choosing a
letter.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
