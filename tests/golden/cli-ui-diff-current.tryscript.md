---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: What a Diff Shows in Diff and in Current

Every file bar with a text diff has a **Diff | Current** chooser at the start of its end
group, before a rendered file’s **Rendered | Source**. **Diff** is the diff as it was
before the chooser existed.
**Current** shows the new version alone: a code body draws only the new file’s lines, in
one column whatever the layout, each hunk’s header naming the new side’s range, added
lines marked `+` and no removed line drawn; a Rendered Markdown body keeps its added
blocks and keys and hides its removed ones; a YAML or JSON tree is drawn without its
removed entries; a deleted file and a file left empty say why they have no lines.
The choice is one for the whole diff, and every bar’s chooser shows it.
It is stored as `diff.show`, so every later diff opens in it, and a stored value that is
not a choice opens **Diff**. A file’s **Rendered | Source** stays its own and is not
stored. The file whose chooser was used keeps its place on the screen; with no chooser
used, as for `N`, the file at the pane’s top keeps its place.
While the diff shows **Current**, the layout control keeps its place and shows the
layout **Diff** draws, its chips `aria-disabled` and saying why, and neither they nor
`L` change anything; **Diff** comes back in that layout.
`N` chooses the other chip, through the same path as a click.
The diff attaches it once, through the SDK’s shortcut surface, on the chip it would
select in the chooser of the file at the pane’s top, or, when that file has none, of the
next file that has one, or else of the one before it, and moves it as the reader scrolls
and after each draw.
A file with no text diff, such as a binary file, has no chooser.

This browserless session loads the production `builtin_plugins/diff/diff-view.js`,
`builtin_plugins/diff/diff-markdown.js`, and `builtin_plugins/diff/diff-structured.js`,
with `static/inert-html.js` and the structured plugin’s tree helpers, and mounts a
comparison of six files into a small element tree.
The rendered files’ answers are the server’s projections recorded in
`tests/fixtures/diff-markdown-responses.json` and
`tests/fixtures/diff-structured-responses.json`. The chip family, the preference store,
and the shortcut registry are stand-ins, and the geometry is a model: a 600 px pane, a
30 px file bar, and 20 px rows.
Each step prints what the diff shows, each bar’s chooser, the layout control, where `N`
and `L` sit, what was written to the preferences, and what each file draws when the step
changed it.

```console
$ node tests/dom/diff-current-session.js
{
  "steps": [
    {
      "step": "a reader who never chose opens Diff, today's view",
      "shows": "diff",
      "Diff | Current": "*Diff | Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split",
        "*Unified"
      ],
      "keys": [
        "N on docs/guide.md's Current",
        "L on the toolbar's Split"
      ],
      "written": [],
      "files": {
        "docs/guide.md": {
          "nothing": "while its Rendered loads"
        },
        "a.py": {
          "source": [
            "@@ -3,3 +3,4 @@ def f():",
            "3 3 | def f():",
            "4 - |-    return 1",
            "- 4 |+    x = 2",
            "- 5 |+    return x",
            "5 6 | "
          ]
        },
        "config/app.yaml": {
          "nothing": "while its Rendered loads"
        },
        "old.txt": {
          "source": [
            "@@ -1,2 +0,0 @@",
            "1 - |-first",
            "2 - |-second"
          ]
        },
        "notes.txt": {
          "source": [
            "@@ -1,2 +0,0 @@",
            "1 - |-a note",
            "2 - |-another"
          ]
        },
        "logo.png": {
          "source": [
            "says: Binary file; no textual diff."
          ]
        }
      }
    },
    {
      "step": "the rendered files arrive, their removed blocks, keys and entries among the rest",
      "shows": "diff",
      "Diff | Current": "*Diff | Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split",
        "*Unified"
      ],
      "keys": [
        "N on docs/guide.md's Current",
        "L on the toolbar's Split"
      ],
      "written": [],
      "files": {
        "docs/guide.md": {
          "rendered": [
            "front matter removed: owner = docs",
            "front matter added: owner = platform",
            "front matter context: title = Guide",
            "context: Guide",
            "removed: Read the setup notes first.",
            "added: Read the first setup notes first.",
            "context: Unchanged paragraph 0.",
            "context: Unchanged paragraph 1.",
            "[5 unchanged blocks]",
            "context: Unchanged paragraph 7.",
            "context: [image]",
            "removed: The old closing line.",
            "added: The new closing line."
          ]
        },
        "config/app.yaml": {
          "rendered": [
            "modified: {4 keys}",
            "  context: name: \"demo\"",
            "  removed: version: 3",
            "  added: version: 4",
            "  modified: services: {1 keys}",
            "    modified: web: {2 keys}",
            "      context: image: \"nginx\"",
            "      modified: ports: [2 items]",
            "        context: - 80",
            "        added: - 443",
            "    removed: db: {2 keys}",
            "      removed: image: \"postgres\"",
            "      removed: port: 5432",
            "  context: flags: [\"fast\", \"safe\"]"
          ]
        }
      }
    },
    {
      "step": "a.py's bar 100 px down: the Markdown file is at the pane's top, and N stays on it",
      "shows": "diff",
      "Diff | Current": "*Diff | Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split",
        "*Unified"
      ],
      "keys": [
        "N on docs/guide.md's Current",
        "L on the toolbar's Split"
      ],
      "written": [],
      "files": {}
    },
    {
      "step": "Current, chosen on a.py: every file shows its new version, stored for every diff",
      "place": "a.py's bar 100 px down before, 100 px after",
      "shows": "current",
      "Diff | Current": "Diff | *Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split (unavailable: Split, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)",
        "*Unified (unavailable: Unified, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)"
      ],
      "keys": [
        "N on docs/guide.md's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=current"
      ],
      "files": {
        "docs/guide.md": {
          "rendered": [
            "front matter added: owner = platform",
            "front matter context: title = Guide",
            "context: Guide",
            "added: Read the first setup notes first.",
            "context: Unchanged paragraph 0.",
            "context: Unchanged paragraph 1.",
            "[5 unchanged blocks]",
            "context: Unchanged paragraph 7.",
            "context: [image]",
            "added: The new closing line."
          ]
        },
        "a.py": {
          "source": [
            "@@ +3,4 @@ def f():",
            "3 | def f():",
            "4 |+    x = 2",
            "5 |+    return x",
            "6 | "
          ]
        },
        "config/app.yaml": {
          "rendered": [
            "modified: {4 keys}",
            "  context: name: \"demo\"",
            "  added: version: 4",
            "  modified: services: {1 keys}",
            "    modified: web: {2 keys}",
            "      context: image: \"nginx\"",
            "      modified: ports: [2 items]",
            "        context: - 80",
            "        added: - 443",
            "  context: flags: [\"fast\", \"safe\"]"
          ]
        },
        "old.txt": {
          "source": [
            "says: This file was deleted, so it has no current version."
          ]
        },
        "notes.txt": {
          "source": [
            "says: This file is empty now."
          ]
        }
      }
    },
    {
      "step": "the Markdown file's Source in Current: the new file's lines alone",
      "shows": "current",
      "Diff | Current": "Diff | *Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split (unavailable: Split, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)",
        "*Unified (unavailable: Unified, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)"
      ],
      "keys": [
        "N on docs/guide.md's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=current"
      ],
      "files": {
        "docs/guide.md": {
          "source": [
            "@@ +1,4 @@",
            "1 | ---",
            "2 |+owner: platform",
            "3 | title: Guide",
            "4 | ---",
            "@@ +6,4 @@",
            "6 | # Guide",
            "7 | ",
            "8 |+Read the [first setup notes](setup.md) first.",
            "9 | ",
            "@@ +30,3 @@",
            "30 | ![diagram](diagram.png)",
            "31 | ",
            "32 |+The <ins>new</ins> closing line."
          ]
        }
      }
    },
    {
      "step": "and its Rendered again: Rendered | Source is the file's own, unstored",
      "shows": "current",
      "Diff | Current": "Diff | *Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split (unavailable: Split, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)",
        "*Unified (unavailable: Unified, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)"
      ],
      "keys": [
        "N on docs/guide.md's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=current"
      ],
      "files": {
        "docs/guide.md": {
          "rendered": [
            "front matter added: owner = platform",
            "front matter context: title = Guide",
            "context: Guide",
            "added: Read the first setup notes first.",
            "context: Unchanged paragraph 0.",
            "context: Unchanged paragraph 1.",
            "[5 unchanged blocks]",
            "context: Unchanged paragraph 7.",
            "context: [image]",
            "added: The new closing line."
          ]
        }
      }
    },
    {
      "step": "Split clicked in Current: nothing changes, and nothing is written",
      "shows": "current",
      "Diff | Current": "Diff | *Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split (unavailable: Split, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)",
        "*Unified (unavailable: Unified, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)"
      ],
      "keys": [
        "N on docs/guide.md's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=current"
      ],
      "files": {}
    },
    {
      "step": "nor does L",
      "shows": "current",
      "Diff | Current": "Diff | *Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split (unavailable: Split, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)",
        "*Unified (unavailable: Unified, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)"
      ],
      "keys": [
        "N on docs/guide.md's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=current"
      ],
      "files": {}
    },
    {
      "step": "N: Diff again, stored",
      "place": "the Markdown file's bar -110 px from the pane's top before, -110 px after",
      "shows": "diff",
      "Diff | Current": "*Diff | Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split",
        "*Unified"
      ],
      "keys": [
        "N on docs/guide.md's Current",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=current",
        "diff.show=diff"
      ],
      "files": {
        "docs/guide.md": {
          "rendered": [
            "front matter removed: owner = docs",
            "front matter added: owner = platform",
            "front matter context: title = Guide",
            "context: Guide",
            "removed: Read the setup notes first.",
            "added: Read the first setup notes first.",
            "context: Unchanged paragraph 0.",
            "context: Unchanged paragraph 1.",
            "[5 unchanged blocks]",
            "context: Unchanged paragraph 7.",
            "context: [image]",
            "removed: The old closing line.",
            "added: The new closing line."
          ]
        },
        "a.py": {
          "source": [
            "@@ -3,3 +3,4 @@ def f():",
            "3 3 | def f():",
            "4 - |-    return 1",
            "- 4 |+    x = 2",
            "- 5 |+    return x",
            "5 6 | "
          ]
        },
        "config/app.yaml": {
          "rendered": [
            "modified: {4 keys}",
            "  context: name: \"demo\"",
            "  removed: version: 3",
            "  added: version: 4",
            "  modified: services: {1 keys}",
            "    modified: web: {2 keys}",
            "      context: image: \"nginx\"",
            "      modified: ports: [2 items]",
            "        context: - 80",
            "        added: - 443",
            "    removed: db: {2 keys}",
            "      removed: image: \"postgres\"",
            "      removed: port: 5432",
            "  context: flags: [\"fast\", \"safe\"]"
          ]
        },
        "old.txt": {
          "source": [
            "@@ -1,2 +0,0 @@",
            "1 - |-first",
            "2 - |-second"
          ]
        },
        "notes.txt": {
          "source": [
            "@@ -1,2 +0,0 @@",
            "1 - |-a note",
            "2 - |-another"
          ]
        }
      }
    },
    {
      "step": "old.txt at the pane's top: N's badge is on its chooser",
      "shows": "diff",
      "Diff | Current": "*Diff | Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split",
        "*Unified"
      ],
      "keys": [
        "N on old.txt's Current",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=current",
        "diff.show=diff"
      ],
      "files": {}
    },
    {
      "step": "logo.png, with no text diff, at the top: N is on the file before it",
      "shows": "diff",
      "Diff | Current": "*Diff | Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split",
        "*Unified"
      ],
      "keys": [
        "N on notes.txt's Current",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=current",
        "diff.show=diff"
      ],
      "files": {}
    },
    {
      "step": "Split chosen in Diff",
      "shows": "diff",
      "Diff | Current": "*Diff | Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "*Split",
        "Unified"
      ],
      "keys": [
        "N on docs/guide.md's Current",
        "L on the toolbar's Unified"
      ],
      "written": [
        "diff.show=current",
        "diff.show=diff",
        "diff.layout=split"
      ],
      "files": {
        "a.py": {
          "source": [
            "@@ -3,3 +3,4 @@ def f():",
            "4 Split rows"
          ]
        },
        "old.txt": {
          "source": [
            "@@ -1,2 +0,0 @@",
            "2 Split rows"
          ]
        },
        "notes.txt": {
          "source": [
            "@@ -1,2 +0,0 @@",
            "2 Split rows"
          ]
        }
      }
    },
    {
      "step": "Current from Split: one column, and the layout keeps Split to come back to",
      "shows": "current",
      "Diff | Current": "Diff | *Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "*Split (unavailable: Split, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)",
        "Unified (unavailable: Unified, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)"
      ],
      "keys": [
        "N on docs/guide.md's Diff",
        "L on the toolbar's Unified"
      ],
      "written": [
        "diff.show=current",
        "diff.show=diff",
        "diff.layout=split",
        "diff.show=current"
      ],
      "files": {
        "docs/guide.md": {
          "rendered": [
            "front matter added: owner = platform",
            "front matter context: title = Guide",
            "context: Guide",
            "added: Read the first setup notes first.",
            "context: Unchanged paragraph 0.",
            "context: Unchanged paragraph 1.",
            "[5 unchanged blocks]",
            "context: Unchanged paragraph 7.",
            "context: [image]",
            "added: The new closing line."
          ]
        },
        "a.py": {
          "source": [
            "@@ +3,4 @@ def f():",
            "3 | def f():",
            "4 |+    x = 2",
            "5 |+    return x",
            "6 | "
          ]
        },
        "config/app.yaml": {
          "rendered": [
            "modified: {4 keys}",
            "  context: name: \"demo\"",
            "  added: version: 4",
            "  modified: services: {1 keys}",
            "    modified: web: {2 keys}",
            "      context: image: \"nginx\"",
            "      modified: ports: [2 items]",
            "        context: - 80",
            "        added: - 443",
            "  context: flags: [\"fast\", \"safe\"]"
          ]
        },
        "old.txt": {
          "source": [
            "says: This file was deleted, so it has no current version."
          ]
        },
        "notes.txt": {
          "source": [
            "says: This file is empty now."
          ]
        }
      }
    },
    {
      "step": "Diff: Split again",
      "shows": "diff",
      "Diff | Current": "*Diff | Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "*Split",
        "Unified"
      ],
      "keys": [
        "N on docs/guide.md's Current",
        "L on the toolbar's Unified"
      ],
      "written": [
        "diff.show=current",
        "diff.show=diff",
        "diff.layout=split",
        "diff.show=current",
        "diff.show=diff"
      ],
      "files": {
        "docs/guide.md": {
          "rendered": [
            "front matter removed: owner = docs",
            "front matter added: owner = platform",
            "front matter context: title = Guide",
            "context: Guide",
            "removed: Read the setup notes first.",
            "added: Read the first setup notes first.",
            "context: Unchanged paragraph 0.",
            "context: Unchanged paragraph 1.",
            "[5 unchanged blocks]",
            "context: Unchanged paragraph 7.",
            "context: [image]",
            "removed: The old closing line.",
            "added: The new closing line."
          ]
        },
        "a.py": {
          "source": [
            "@@ -3,3 +3,4 @@ def f():",
            "4 Split rows"
          ]
        },
        "config/app.yaml": {
          "rendered": [
            "modified: {4 keys}",
            "  context: name: \"demo\"",
            "  removed: version: 3",
            "  added: version: 4",
            "  modified: services: {1 keys}",
            "    modified: web: {2 keys}",
            "      context: image: \"nginx\"",
            "      modified: ports: [2 items]",
            "        context: - 80",
            "        added: - 443",
            "    removed: db: {2 keys}",
            "      removed: image: \"postgres\"",
            "      removed: port: 5432",
            "  context: flags: [\"fast\", \"safe\"]"
          ]
        },
        "old.txt": {
          "source": [
            "@@ -1,2 +0,0 @@",
            "2 Split rows"
          ]
        },
        "notes.txt": {
          "source": [
            "@@ -1,2 +0,0 @@",
            "2 Split rows"
          ]
        }
      }
    },
    {
      "step": "disposed: every chooser's listener is unbound, and N and L are detached",
      "keys": [
        "detached",
        "detached"
      ],
      "bound": 0
    },
    {
      "step": "a later diff opens in Current, the stored choice",
      "shows": "current",
      "Diff | Current": "Diff | *Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "Split (unavailable: Split, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)",
        "*Unified (unavailable: Unified, unavailable. Current shows the new version in one column; choose Diff for Split or Unified.)"
      ],
      "keys": [
        "N on docs/guide.md's Diff",
        "L on the toolbar's Split"
      ],
      "written": [],
      "files": {
        "docs/guide.md": {
          "rendered": [
            "front matter added: owner = platform",
            "front matter context: title = Guide",
            "context: Guide",
            "added: Read the first setup notes first.",
            "context: Unchanged paragraph 0.",
            "context: Unchanged paragraph 1.",
            "[5 unchanged blocks]",
            "context: Unchanged paragraph 7.",
            "context: [image]",
            "added: The new closing line."
          ]
        },
        "a.py": {
          "source": [
            "@@ +3,4 @@ def f():",
            "3 | def f():",
            "4 |+    x = 2",
            "5 |+    return x",
            "6 | "
          ]
        },
        "config/app.yaml": {
          "rendered": [
            "modified: {4 keys}",
            "  context: name: \"demo\"",
            "  added: version: 4",
            "  modified: services: {1 keys}",
            "    modified: web: {2 keys}",
            "      context: image: \"nginx\"",
            "      modified: ports: [2 items]",
            "        context: - 80",
            "        added: - 443",
            "  context: flags: [\"fast\", \"safe\"]"
          ]
        },
        "old.txt": {
          "source": [
            "says: This file was deleted, so it has no current version."
          ]
        },
        "notes.txt": {
          "source": [
            "says: This file is empty now."
          ]
        },
        "logo.png": {
          "source": [
            "says: Binary file; no textual diff."
          ]
        }
      }
    },
    {
      "step": "a stored value that is not a choice opens Diff, and is not rewritten",
      "shows": "diff",
      "Diff | Current": "*Diff | Current on 5 of 6 bars (logo.png has none)",
      "layout": [
        "*Split",
        "Unified"
      ],
      "keys": [
        "N on docs/guide.md's Current",
        "L on the toolbar's Unified"
      ],
      "written": [],
      "files": {
        "docs/guide.md": {
          "nothing": "while its Rendered loads"
        },
        "a.py": {
          "source": [
            "@@ -3,3 +3,4 @@ def f():",
            "4 Split rows"
          ]
        },
        "config/app.yaml": {
          "nothing": "while its Rendered loads"
        },
        "old.txt": {
          "source": [
            "@@ -1,2 +0,0 @@",
            "2 Split rows"
          ]
        },
        "notes.txt": {
          "source": [
            "@@ -1,2 +0,0 @@",
            "2 Split rows"
          ]
        },
        "logo.png": {
          "source": [
            "says: Binary file; no textual diff."
          ]
        }
      }
    }
  ]
}
? 0
```
