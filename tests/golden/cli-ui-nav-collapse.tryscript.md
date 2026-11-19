---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Hiding the Navigation Pane

`\` hides the navigation pane from anywhere outside a text field, through the chevron’s own path, and Shift-`\`,
which types `|` on a US keyboard, is the same key by its physical key
(docs/design-system.md, “Hiding the Navigation Pane”). The session runs the production
shortcut registry, shell keymap, and `static/nav-collapse.js` on the key reveal
session’s stand-in shell.
Hidden, the pane is inert, so the keys of its controls, `0`, `F`, and the filters’
numbers, leave the live keymap, and focus on a tree row moves to the main page;
`\` stays live on the chevron, which the main frame holds, and its label says what it does next. Shown again, the pane’s keys come back. `cli-ui-key-reveal.tryscript.md`shows the key live on every screen and its badge beside the chevron;`tests/test_nav_collapse_chrome.py`
measures the slide in headless Chrome.

```console
$ node tests/dom/nav-collapse-session.js
{
  "part": "nav",
  "steps": [
    {
      "step": "a file is open with the navigation pane shown",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "\\ hides the navigation pane, and only the main page's keys stay live",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["\\","shell.nav-toggle","Show navigation"],
        ["V","view-tabs.v","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"]
      ],
      "numbers": [],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "\\",
        "handled": true
      },
      "nav": {
        "inert": true,
        "expanded": "false",
        "label": "Show navigation",
        "focus": "preview-pane"
      },
      "did": ["hid the navigation pane"]
    },
    {
      "step": "Shift-\\, which types | on a US keyboard, shows it again",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "|",
        "handled": true
      },
      "nav": {
        "inert": false,
        "expanded": "true",
        "label": "Hide navigation"
      },
      "did": ["showed the navigation pane"]
    }
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
