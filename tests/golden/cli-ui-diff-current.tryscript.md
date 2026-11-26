---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Diff, Excerpt, and Full

The toolbar groups **Diff | Excerpt | Full** before **Split | Unified**. Docs fixes the
layout and shows just the presentation chooser.
A patch without a complete snapshot offers Diff and Excerpt.
**Diff** shows additions and removals with context.
**Excerpt** shows the new side around the changes in one column, using markers for
deletions. **Full** draws the whole new side when available.
A deleted file and a file left empty explain their status.
A Markdown, YAML, or JSON file has its own **Rendered | Source** choice, which survives
a change in presentation.

Changes, commits, and patches start on Diff and share `diff.show`. Docs prefers Full and
uses `github.docs.show`. Unknown preference values fall back to those defaults.
The line or block at the top keeps its place, using the next drawn row when needed.
In either reading mode the layout chips stay visible and disabled, and reopening Diff
restores the chosen layout and focus.
`N` switches between Diff and Excerpt.
The shortcut follows the chip it activates.

This browserless session loads the production `builtin_plugins/diff/diff-view.js`,
`builtin_plugins/diff/diff-markdown.js`, and `builtin_plugins/diff/diff-structured.js`,
with `static/inert-html.js` and the structured plugin’s tree helpers, and mounts a
comparison of six files into a small element tree, as Changes mounts it and as a pull
request’s Docs tab does, with the layout fixed, **Full** its default, and its own
preference. The rendered files’ answers are the server’s projections recorded in
`tests/fixtures/diff-markdown-responses.json` and
`tests/fixtures/diff-structured-responses.json`. The chip family, the preference store,
and the shortcut registry are stand-ins, and the geometry is a model: a 600 px pane, a
30 px toolbar and file bar, and 20 px rows.
Each step prints what the diff shows, what its toolbar holds (the choosers’ group as a
list of its own), where `N` and `L` sit, what was written to the preferences, what each
file bar’s end group holds when that changed, and what each file draws when the step
changed it; a step that tests a place prints the row at the pane’s top and where it is.
The steps across surfaces share one reader’s store and print no drawings.

```console
$ node tests/dom/diff-current-session.js
{
  "steps": [
    {
      "step": "a reader who never chose opens Diff, today's view",
      "shows": "diff",
      "toolbar": [
        [
          "Comparison view: *Diff | Excerpt | Full",
          "Split | Unified: Split | *Unified"
        ]
      ],
      "keys": [
        "N on the toolbar's Excerpt",
        "L on the toolbar's Split"
      ],
      "written": [],
      "bar ends": {
        "docs/guide.md": "*Rendered | Source",
        "a.py": "nothing",
        "config/app.yaml": "*Rendered | Source",
        "old.txt": "nothing",
        "notes.txt": "nothing",
        "logo.png": "nothing"
      },
      "files": {
        "docs/guide.md": {
          "nothing": "while its rendered view loads"
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
          "nothing": "while its rendered view loads"
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
      "toolbar": [
        [
          "Comparison view: *Diff | Excerpt | Full",
          "Split | Unified: Split | *Unified"
        ]
      ],
      "keys": [
        "N on the toolbar's Excerpt",
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
      "step": "Excerpt, chosen in the toolbar: every file shows its new version around the changes, stored as diff.show",
      "place": "the first file's bar 30 px down before, 30 px after",
      "shows": "current",
      "toolbar": [
        [
          "Comparison view: Diff | *Excerpt | Full",
          "Split | Unified: Split (unavailable) | *Unified (unavailable)"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=excerpt"
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
            "@@ +3,4 @@",
            "3 | def f():",
            "4 |+    x = 2",
            "5 |+    return x",
            "6 | "
          ]
        },
        "config/app.yaml": {
          "rendered": [
            "modified: {4 keys}",
            "  removed: version: removed",
            "  added: version: 4",
            "  modified: services: {1 keys}",
            "    modified: web: {2 keys}",
            "      modified: ports: [2 items]",
            "        added: - 443",
            "    removed: db: removed"
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
      "step": "the Markdown file's Source in Excerpt: the new file's lines around the changes",
      "shows": "current",
      "toolbar": [
        [
          "Comparison view: Diff | *Excerpt | Full",
          "Split | Unified: Split (unavailable) | *Unified (unavailable)"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=excerpt"
      ],
      "bar ends": {
        "docs/guide.md": "Rendered | *Source",
        "a.py": "nothing",
        "config/app.yaml": "*Rendered | Source",
        "old.txt": "nothing",
        "notes.txt": "nothing",
        "logo.png": "nothing"
      },
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
      "step": "Rendered again keeps the comparison's Excerpt mode",
      "shows": "current",
      "toolbar": [
        [
          "Comparison view: Diff | *Excerpt | Full",
          "Split | Unified: Split (unavailable) | *Unified (unavailable)"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=excerpt"
      ],
      "bar ends": {
        "docs/guide.md": "*Rendered | Source",
        "a.py": "nothing",
        "config/app.yaml": "*Rendered | Source",
        "old.txt": "nothing",
        "notes.txt": "nothing",
        "logo.png": "nothing"
      },
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
      "step": "Split clicked in Excerpt: nothing changes, and nothing is written",
      "shows": "current",
      "toolbar": [
        [
          "Comparison view: Diff | *Excerpt | Full",
          "Split | Unified: Split (unavailable) | *Unified (unavailable)"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=excerpt"
      ],
      "files": {}
    },
    {
      "step": "nor does L",
      "shows": "current",
      "toolbar": [
        [
          "Comparison view: Diff | *Excerpt | Full",
          "Split | Unified: Split (unavailable) | *Unified (unavailable)"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=excerpt"
      ],
      "files": {}
    },
    {
      "step": "a.py's bar 100 px down: N stays on the toolbar's chooser",
      "pane's top": "Unchanged paragraph 1., at 0 px",
      "shows": "current",
      "toolbar": [
        [
          "Comparison view: Diff | *Excerpt | Full",
          "Split | Unified: Split (unavailable) | *Unified (unavailable)"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=excerpt"
      ],
      "files": {}
    },
    {
      "step": "N: Diff again, stored, and the block at the pane's top keeps its place",
      "place": "Unchanged paragraph 1. is 0 px from the pane's top before, 0 px after; the Markdown file's bar -110 px before, -150 px after",
      "shows": "diff",
      "toolbar": [
        [
          "Comparison view: *Diff | Excerpt | Full",
          "Split | Unified: Split | *Unified"
        ]
      ],
      "keys": [
        "N on the toolbar's Excerpt",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=excerpt",
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
      "step": "logo.png at the pane's top: N has not moved",
      "shows": "diff",
      "toolbar": [
        [
          "Comparison view: *Diff | Excerpt | Full",
          "Split | Unified: Split | *Unified"
        ]
      ],
      "keys": [
        "N on the toolbar's Excerpt",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=excerpt",
        "diff.show=diff"
      ]
    },
    {
      "step": "a.py's removed line at the pane's top, in Diff",
      "pane's top": "return 1, at 0 px",
      "next line": "x = 2, at 20 px",
      "shows": "diff",
      "toolbar": [
        [
          "Comparison view: *Diff | Excerpt | Full",
          "Split | Unified: Split | *Unified"
        ]
      ],
      "keys": [
        "N on the toolbar's Excerpt",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=excerpt",
        "diff.show=diff"
      ]
    },
    {
      "step": "Excerpt: the next line it draws keeps its place",
      "place": "x = 2 is 20 px from the pane's top before, 20 px after",
      "shows": "current",
      "toolbar": [
        [
          "Comparison view: Diff | *Excerpt | Full",
          "Split | Unified: Split (unavailable) | *Unified (unavailable)"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=excerpt",
        "diff.show=diff",
        "diff.show=excerpt"
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
            "@@ +3,4 @@",
            "3 | def f():",
            "4 |+    x = 2",
            "5 |+    return x",
            "6 | "
          ]
        },
        "config/app.yaml": {
          "rendered": [
            "modified: {4 keys}",
            "  removed: version: removed",
            "  added: version: 4",
            "  modified: services: {1 keys}",
            "    modified: web: {2 keys}",
            "      modified: ports: [2 items]",
            "        added: - 443",
            "    removed: db: removed"
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
      "step": "Diff again: the line at the pane's top keeps its place, the removed one below it",
      "place": "def f(): is 0 px from the pane's top before, 0 px after; the removed line at 20 px",
      "shows": "diff",
      "toolbar": [
        [
          "Comparison view: *Diff | Excerpt | Full",
          "Split | Unified: Split | *Unified"
        ]
      ],
      "keys": [
        "N on the toolbar's Excerpt",
        "L on the toolbar's Split"
      ],
      "written": [
        "diff.show=excerpt",
        "diff.show=diff",
        "diff.show=excerpt",
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
      "step": "Split chosen in Diff",
      "shows": "diff",
      "toolbar": [
        [
          "Comparison view: *Diff | Excerpt | Full",
          "Split | Unified: *Split | Unified"
        ]
      ],
      "keys": [
        "N on the toolbar's Excerpt",
        "L on the toolbar's Unified"
      ],
      "written": [
        "diff.show=excerpt",
        "diff.show=diff",
        "diff.show=excerpt",
        "diff.show=diff"
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
      "step": "Excerpt from Split, by N with focus on Split: one column, the layout kept",
      "focus": "Split | Unified's Split",
      "shows": "current",
      "toolbar": [
        [
          "Comparison view: Diff | *Excerpt | Full",
          "Split | Unified: *Split (unavailable) | Unified (unavailable)"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "L on the toolbar's Unified"
      ],
      "written": [
        "diff.show=excerpt",
        "diff.show=diff",
        "diff.show=excerpt",
        "diff.show=diff",
        "diff.show=excerpt"
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
            "@@ +3,4 @@",
            "3 | def f():",
            "4 |+    x = 2",
            "5 |+    return x",
            "6 | "
          ]
        },
        "config/app.yaml": {
          "rendered": [
            "modified: {4 keys}",
            "  removed: version: removed",
            "  added: version: 4",
            "  modified: services: {1 keys}",
            "    modified: web: {2 keys}",
            "      modified: ports: [2 items]",
            "        added: - 443",
            "    removed: db: removed"
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
      "toolbar": [
        [
          "Comparison view: *Diff | Excerpt | Full",
          "Split | Unified: *Split | Unified"
        ]
      ],
      "keys": [
        "N on the toolbar's Excerpt",
        "L on the toolbar's Unified"
      ],
      "written": [
        "diff.show=excerpt",
        "diff.show=diff",
        "diff.show=excerpt",
        "diff.show=diff",
        "diff.show=excerpt",
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
      "step": "Docs, never chosen there: Full, its default, with no layout control",
      "shows": "full",
      "toolbar": [
        [
          "Comparison view: Diff | Excerpt | *Full"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "not attached"
      ],
      "written": [],
      "bar ends": {
        "docs/guide.md": "*Rendered | Source",
        "a.py": "nothing",
        "config/app.yaml": "*Rendered | Source",
        "old.txt": "nothing",
        "notes.txt": "nothing",
        "logo.png": "nothing"
      },
      "files": {
        "docs/guide.md": {
          "rendered": [
            "front matter added: owner = platform",
            "front matter context: title = Guide",
            "context: Guide",
            "added: Read the first setup notes first.",
            "context: Unchanged paragraph 0.",
            "context: Unchanged paragraph 1.",
            "context: Unchanged paragraph 2.",
            "context: Unchanged paragraph 3.",
            "context: Unchanged paragraph 4.",
            "context: Unchanged paragraph 5.",
            "context: Unchanged paragraph 6.",
            "context: Unchanged paragraph 7.",
            "context: [image]",
            "added: The new closing line."
          ]
        },
        "a.py": {
          "source": [
            "@@ +3,4 @@",
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
      "step": "Changes: Excerpt chosen, stored as diff.show",
      "shows": "current",
      "toolbar": [
        [
          "Comparison view: Diff | *Excerpt | Full",
          "Split | Unified: *Split (unavailable) | Unified (unavailable)"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "L on the toolbar's Unified"
      ],
      "written": [
        "diff.show=excerpt"
      ]
    },
    {
      "step": "Docs opens on its own default, Full, which Changes did not set",
      "shows": "full",
      "toolbar": [
        [
          "Comparison view: Diff | Excerpt | *Full"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "not attached"
      ],
      "written": []
    },
    {
      "step": "Docs: Diff chosen, stored as github.docs.show",
      "shows": "diff",
      "toolbar": [
        [
          "Comparison view: *Diff | Excerpt | Full"
        ]
      ],
      "keys": [
        "N on the toolbar's Excerpt",
        "not attached"
      ],
      "written": [
        "github.docs.show=diff"
      ]
    },
    {
      "step": "Changes again: Excerpt, its own choice, which Docs did not move",
      "shows": "current",
      "toolbar": [
        [
          "Comparison view: Diff | *Excerpt | Full",
          "Split | Unified: *Split (unavailable) | Unified (unavailable)"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "L on the toolbar's Unified"
      ],
      "written": []
    },
    {
      "step": "Docs again: Diff, its own choice",
      "shows": "diff",
      "toolbar": [
        [
          "Comparison view: *Diff | Excerpt | Full"
        ]
      ],
      "keys": [
        "N on the toolbar's Excerpt",
        "not attached"
      ],
      "written": []
    },
    {
      "step": "what the store holds",
      "stored": {
        "diff.show": "excerpt",
        "github.docs.show": "diff"
      }
    },
    {
      "step": "Changes, a stored value that is not a choice: Diff, its default",
      "shows": "diff",
      "toolbar": [
        [
          "Comparison view: *Diff | Excerpt | Full",
          "Split | Unified: *Split | Unified"
        ]
      ],
      "keys": [
        "N on the toolbar's Excerpt",
        "L on the toolbar's Unified"
      ],
      "written": []
    },
    {
      "step": "Docs, a stored value that is not a choice: Full, its default",
      "shows": "full",
      "toolbar": [
        [
          "Comparison view: Diff | Excerpt | *Full"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "not attached"
      ],
      "written": []
    },
    {
      "step": "Full source includes lines before and after the hunks",
      "shows": "full",
      "toolbar": [
        [
          "Comparison view: Diff | Excerpt | *Full",
          "Split | Unified: *Split (unavailable) | Unified (unavailable)"
        ]
      ],
      "keys": [
        "N on the toolbar's Diff",
        "L on the toolbar's Unified"
      ],
      "written": [
        "diff.show=full"
      ],
      "bar ends": {
        "docs/guide.md": "*Rendered | Source",
        "a.py": "nothing",
        "config/app.yaml": "*Rendered | Source",
        "old.txt": "nothing",
        "notes.txt": "nothing",
        "logo.png": "nothing"
      },
      "files": {
        "docs/guide.md": {
          "rendered": [
            "front matter added: owner = platform",
            "front matter context: title = Guide",
            "context: Guide",
            "added: Read the first setup notes first.",
            "context: Unchanged paragraph 0.",
            "context: Unchanged paragraph 1.",
            "context: Unchanged paragraph 2.",
            "context: Unchanged paragraph 3.",
            "context: Unchanged paragraph 4.",
            "context: Unchanged paragraph 5.",
            "context: Unchanged paragraph 6.",
            "context: Unchanged paragraph 7.",
            "context: [image]",
            "added: The new closing line."
          ]
        },
        "a.py": {
          "source": [
            "1 | # Before the first hunk",
            "2 | ",
            "3 | def f():",
            "4 |+    x = 2",
            "5 |+    return x",
            "6 | ",
            "7 | # After the last hunk"
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
    }
  ]
}
? 0
```
