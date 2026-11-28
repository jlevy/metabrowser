---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: Markdown frontmatter views

## Test: switch frontmatter and independently opened code fences between views

```console
$ node tests/dom/markdown-frontmatter-views-session.js
[
  {
    "article": "trusted",
    "opened": [
      [],
      [
        "roles"
      ],
      [
        "title"
      ],
      [
        "roles"
      ]
    ],
    "row": "title: Workshop",
    "copied": "[host,\r\n editor]",
    "prose": "Readable prose"
  },
  {
    "article": "sanitized",
    "opened": [
      [],
      [
        "roles"
      ],
      [
        "title"
      ],
      [
        "roles"
      ]
    ],
    "row": "title: Workshop",
    "copied": "[host,\r\n editor]",
    "prose": "Readable prose"
  }
]
{
  "reads": [
    [
      4,
      "Table"
    ],
    [
      11,
      "Table"
    ],
    [
      11,
      "Tree"
    ],
    [
      11,
      "Source"
    ]
  ],
  "source": "{\"key\": null}\r\n"
}
? 0
```
