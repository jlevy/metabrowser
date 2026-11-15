# Keyboard Shortcuts

Every Metabrowser shortcut is a single key with no modifier, and Shift changes nothing.
A letter means the same thing wherever it works, and the numbers `1` to `9` reach the
controls on the current screen in reading order.
Press `?` for Help, which lists the keys by what they do, and hold Shift to see each key
on the control it reaches now.

## Letters and Numbers

| Key | Meaning | Works when |
| --- | --- | --- |
| `?` | Help | Always |
| `T` or `/` | Quick Search, the file finder | Always |
| `F` | The Files tab | Always |
| `R` | The Pulls tab: pull Requests | The Pulls tab is shown, for a GitHub repository |
| `H` | The Commits tab: commit History | The served folder is in a Git repository |
| `J` or `K` | Down or up a row | A tree, Commits, Pulls, or changed-file row has focus |
| `N` or `P` | Next or previous item one level up: the pull requests of a stack | A pull request in a stack is open |
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

`tests/test_keymap.py` checks this table against the keys the shell, the plugin
manifests, and the built-in plugins bind.
A letter that appears twice, such as `C`, belongs to two screens never shown together.

## Numbered Controls

Numbers are positional, so `1` reaches a different control on a different screen.
Each control is numbered only while it is shown:

| Screen | Numbered controls |
| --- | --- |
| The Files tab | Modified within (Any age), then File type (Any type); a Git pin has only File type |
| The Pulls tab | Open, Closed, and All, then Reload, which keeps its number while it waits |
| A pull request page | View on GitHub, Browse code, Refresh or Fetch, Switch to the head, and Browse the checkout |

The navigation pane’s numbers come first, so a pull request page’s numbers continue
after those of the tab beside it.
A tenth control gets no number.

Copy buttons, per-file controls such as a changed file’s View file, and controls that
appear only on hover have no key; Tab and the pointer reach them.

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

In Quick Search, Up and Down move through the results, Enter opens one, and Escape
closes it. In Help, `?` or Escape closes it.

## Browser and App Keys

A key held with Command, Control, or Option belongs to the browser, and in the macOS app
to the app’s menus: no Metabrowser shortcut uses one, and the page takes none.
The one exception is Option-Tab inside a dialog or an open menu: the dialog or menu
keeps it, because Safari moves focus with Option-Tab.

Command-R (Control-R or F5 elsewhere) always reloads, whatever has focus.
In the macOS app it is View > Reload Page, which also restarts a folder whose server
failed. The app’s other keys are the ones its menus show, built in
`apps/macos/Sources/Metabrowser/MainMenu.swift`; [the app guide](macos-app.md) describes
the menus.

## For Plugin Authors

A plugin’s view tabs and controls take keys under the same rules.
[Keyboard shortcuts in the plugin guide](plugins.md#keyboard-shortcuts) has the API, and
the [design system](design-system.md#keyboard-shortcuts) has the rules for choosing a
letter.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
