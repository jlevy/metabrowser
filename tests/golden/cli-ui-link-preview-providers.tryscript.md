---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: What a Link Card Says, and What a Rest on a Link Loads

A link in rendered text that opens a page in Metabrowser shows a card when the pointer
rests on it, and the rest starts loading what the link opens.
`static/link-preview-providers.js` answers both for each kind of page: a pull request, a
stack, a commit, a file or a folder, and the list of pull requests.
The
[link preview tooltips plan](../../docs/project/specs/active/plan-2026-11-26-link-preview-tooltips.md)
is the design, and its “Data and Prefetch” table is the reads each kind makes.

This session runs the exact module whole, with the exact modules it reads: the Commits
panel (`static/git-panel.js`), whose commit summary and prefetch it calls, the shared
formatters, the file type registry, and the GitPath codec.
The card’s registry is a stand-in that keeps what each provider registers, and the
session calls each as the card does.
Every read replays the server’s own answer:
`tests/fixtures/link-preview-providers-responses.json`, which
`tests/test_link_preview_providers_session.py` records from the real routes, and the
stacks snapshot the Pulls tab’s session replays.
A read with no recorded answer fails the session.

- `provided` is each kind a provider registered for.
- Each of `summaries` is one rest: the link’s object, what its card says, and the reads
  that rest made. A pull request’s title and state come from the catalog’s exact-number
  search, once a page for each number, and a caller that stops waiting leaves its read
  to land and be kept.
  A stack’s come from one read of the stacks snapshot, reused for a while.
  A commit’s come from the Commits panel’s detail cache, which asks once for a commit
  the repository lacks.
  A file’s and a folder’s come from what the page already holds, with no read, and
  `catalog` says whether the file catalog covered the whole root.
- No summary says what its data does not give: a pull request the catalog does not hold,
  a stack the snapshot does not, a folder the tree has not totaled, and the list have
  none, and a file is missing only from a catalog of the whole root.
- Each of `prefetches` is what one rest started: the reads it made, the plugin assets it
  loaded, and the pages whose View on GitHub answer it asked for.
  A pull request’s record is read with `warm=1`, once a page; a commit is prepared as a
  hover on its row prepares it, and a commit the repository lacks is not.
- `a commit's card and prefetch together` shows the two sharing one read of its detail.
- `requests` is every request any module made, in order, and `aborted` those whose
  signal aborted them before their answer came.

```console
$ node tests/dom/link-preview-providers-session.js
{
  "provided": [
    "pull",
    "stack",
    "commit",
    "file",
    "folder",
    "pulls"
  ],
  "summaries": {
    "a pull request, open": {
      "subject": {
        "kind": "pull",
        "number": 12,
        "tab": "",
        "file": ""
      },
      "summary": {
        "title": "feat(links): preview what a link opens",
        "state": "open"
      },
      "asked": [
        "GET /api/plugin/github/pulls?q=12"
      ]
    },
    "a draft": {
      "subject": {
        "kind": "pull",
        "number": 13,
        "tab": "",
        "file": ""
      },
      "summary": {
        "title": "Draft: a tooltip for every in-app link",
        "state": "draft"
      },
      "asked": [
        "GET /api/plugin/github/pulls?q=13"
      ]
    },
    "a closed one, whose caller stops waiting": {
      "subject": {
        "kind": "pull",
        "number": 14,
        "tab": "",
        "file": ""
      },
      "summary": {
        "rejected": "AbortError"
      },
      "asked": [
        "GET /api/plugin/github/pulls?q=14"
      ]
    },
    "the closed one, rested on again": {
      "subject": {
        "kind": "pull",
        "number": 14,
        "tab": "",
        "file": ""
      },
      "summary": {
        "title": "Retire the native link title",
        "state": "closed"
      },
      "asked": []
    },
    "a merged one": {
      "subject": {
        "kind": "pull",
        "number": 15,
        "tab": "",
        "file": ""
      },
      "summary": {
        "title": "docs: the rule for tooltips on links",
        "state": "merged"
      },
      "asked": [
        "GET /api/plugin/github/pulls?q=15"
      ]
    },
    "one the catalog does not hold": {
      "subject": {
        "kind": "pull",
        "number": 99,
        "tab": "",
        "file": ""
      },
      "summary": null,
      "asked": [
        "GET /api/plugin/github/pulls?q=99"
      ]
    },
    "the open one again": {
      "subject": {
        "kind": "pull",
        "number": 12,
        "tab": "",
        "file": ""
      },
      "summary": {
        "title": "feat(links): preview what a link opens",
        "state": "open"
      },
      "asked": []
    },
    "a changed file in its Changes": {
      "subject": {
        "kind": "pull",
        "number": 12,
        "tab": "files",
        "file": "docs/guide.md"
      },
      "summary": {
        "title": "feat(links): preview what a link opens",
        "state": "open"
      },
      "asked": []
    },
    "a stack the snapshot holds": {
      "subject": {
        "kind": "stack",
        "number": 286,
        "file": ""
      },
      "summary": {
        "title": "Stack change 8",
        "detail": "3 pull requests"
      },
      "asked": [
        "GET /api/plugin/github/stacks"
      ]
    },
    "another, from the same read": {
      "subject": {
        "kind": "stack",
        "number": 290,
        "file": ""
      },
      "summary": {
        "title": "Stack change 10",
        "detail": "3 pull requests"
      },
      "asked": []
    },
    "one the snapshot does not hold": {
      "subject": {
        "kind": "stack",
        "number": 300,
        "file": ""
      },
      "summary": null,
      "asked": []
    },
    "a stack, once the read is too old to reuse": {
      "subject": {
        "kind": "stack",
        "number": 286,
        "file": ""
      },
      "summary": null,
      "asked": [
        "GET /api/plugin/github/stacks"
      ]
    },
    "a commit the repository has": {
      "subject": {
        "kind": "commit",
        "revision": "5ed518dc01e604da80e752ddd5ee4de4b6e14bd1"
      },
      "summary": {
        "title": "docs: write the guide",
        "detail": "Ada Author · 6d ago"
      },
      "asked": [
        "GET /api/git/commit/5ed518dc01e604da80e752ddd5ee4de4b6e14bd1"
      ]
    },
    "a commit it lacks": {
      "subject": {
        "kind": "commit",
        "revision": "0123456789abcdef0123456789abcdef01234567"
      },
      "summary": {
        "missing": "Not in this repository"
      },
      "asked": [
        "GET /api/git/commit/0123456789abcdef0123456789abcdef01234567"
      ]
    },
    "the missing commit again": {
      "subject": {
        "kind": "commit",
        "revision": "0123456789abcdef0123456789abcdef01234567"
      },
      "summary": {
        "missing": "Not in this repository"
      },
      "asked": []
    },
    "a commit, before the Commits panel has loaded": {
      "subject": {
        "kind": "commit",
        "revision": "5ed518dc01e604da80e752ddd5ee4de4b6e14bd1"
      },
      "summary": null,
      "asked": []
    },
    "a file the served tree holds": {
      "subject": {
        "kind": "file",
        "path": "docs/guide.md",
        "opens": "here",
        "target": {
          "path": "docs/guide.md"
        }
      },
      "summary": {
        "detail": "Markdown file"
      },
      "asked": [],
      "catalog": "whole"
    },
    "the same file, opened in the served working tree": {
      "subject": {
        "kind": "file",
        "path": "docs/guide.md",
        "opens": "working-tree",
        "target": {
          "path": "docs/guide.md"
        }
      },
      "summary": {
        "detail": "Markdown file"
      },
      "asked": [],
      "catalog": "whole"
    },
    "a file a whole catalog lacks": {
      "subject": {
        "kind": "file",
        "path": "docs/old-guide.md",
        "opens": "here",
        "target": {
          "path": "docs/old-guide.md"
        }
      },
      "summary": {
        "detail": "Markdown file",
        "missing": "Not in the served files"
      },
      "asked": [],
      "catalog": "whole"
    },
    "the same, while the catalog is still filling": {
      "subject": {
        "kind": "file",
        "path": "docs/old-guide.md",
        "opens": "here",
        "target": {
          "path": "docs/old-guide.md"
        }
      },
      "summary": {
        "detail": "Markdown file"
      },
      "asked": [],
      "catalog": "filling"
    },
    "a name with a percent sign": {
      "subject": {
        "kind": "file",
        "path": "notes/100%.md",
        "opens": "here",
        "target": {
          "path": "notes/100%25.md"
        }
      },
      "summary": {
        "detail": "Markdown file"
      },
      "asked": [],
      "catalog": "whole"
    },
    "a name no file type claims": {
      "subject": {
        "kind": "file",
        "path": "notes/draft.zzz-unclaimed",
        "opens": "here",
        "target": {
          "path": "notes/draft.zzz-unclaimed"
        }
      },
      "summary": null,
      "asked": [],
      "catalog": "whole"
    },
    "a folder the tree has totaled": {
      "subject": {
        "kind": "folder",
        "path": "docs/",
        "opens": "here",
        "target": {
          "path": "docs/"
        }
      },
      "summary": {
        "detail": "1 file · 48 B"
      },
      "asked": [],
      "catalog": "whole"
    },
    "the served root": {
      "subject": {
        "kind": "folder",
        "path": "",
        "opens": "here",
        "target": {
          "path": ""
        }
      },
      "summary": {
        "detail": "3 files · 112 B"
      },
      "asked": [],
      "catalog": "whole"
    },
    "a folder it has not": {
      "subject": {
        "kind": "folder",
        "path": "src/",
        "opens": "here",
        "target": {
          "path": "src/"
        }
      },
      "summary": null,
      "asked": [],
      "catalog": "whole"
    },
    "a file of a pinned revision": {
      "subject": {
        "kind": "file",
        "path": "docs/guide.md",
        "opens": "here",
        "target": {
          "path": "g1-ZG9jcw/g1-Z3VpZGUubWQ"
        }
      },
      "summary": {
        "detail": "Markdown file"
      },
      "asked": [],
      "catalog": "whole"
    },
    "a file the pinned revision lacks": {
      "subject": {
        "kind": "file",
        "path": "docs/old-guide.md",
        "opens": "here",
        "target": {
          "path": "g1-ZG9jcw/g1-b2xkLWd1aWRlLm1k"
        }
      },
      "summary": {
        "detail": "Markdown file",
        "missing": "Not in the served files"
      },
      "asked": [],
      "catalog": "whole"
    },
    "the pull request list": {
      "subject": {
        "kind": "pulls"
      },
      "summary": null,
      "asked": []
    }
  },
  "prefetches": {
    "a pull request": {
      "subject": {
        "kind": "pull",
        "number": 12,
        "tab": "",
        "file": ""
      },
      "asked": [
        "GET /api/plugin/github/pull?number=12&warm=1"
      ],
      "assets": [
        "pull-request"
      ],
      "counterparts": []
    },
    "the same pull request again": {
      "subject": {
        "kind": "pull",
        "number": 12,
        "tab": "files",
        "file": "docs/guide.md"
      },
      "asked": [],
      "assets": [
        "pull-request"
      ],
      "counterparts": []
    },
    "a stack": {
      "subject": {
        "kind": "stack",
        "number": 286,
        "file": ""
      },
      "asked": [],
      "assets": [
        "pull-stack"
      ],
      "counterparts": []
    },
    "a commit the repository has": {
      "subject": {
        "kind": "commit",
        "revision": "5ed518dc01e604da80e752ddd5ee4de4b6e14bd1"
      },
      "asked": [
        "GET /api/plugin/diff/comparison?revision=5ed518dc01e604da80e752ddd5ee4de4b6e14bd1"
      ],
      "assets": [
        "diff"
      ],
      "counterparts": []
    },
    "a commit it lacks": {
      "subject": {
        "kind": "commit",
        "revision": "0123456789abcdef0123456789abcdef01234567"
      },
      "asked": [],
      "assets": [],
      "counterparts": []
    },
    "a file": {
      "subject": {
        "kind": "file",
        "path": "docs/guide.md",
        "opens": "here",
        "target": {
          "path": "docs/guide.md"
        }
      },
      "asked": [],
      "assets": [],
      "counterparts": [
        "/view/docs/guide.md"
      ]
    },
    "a folder": {
      "subject": {
        "kind": "folder",
        "path": "docs/",
        "opens": "here",
        "target": {
          "path": "docs/"
        }
      },
      "asked": [],
      "assets": [],
      "counterparts": [
        "/view/docs/"
      ]
    },
    "the served root": {
      "subject": {
        "kind": "folder",
        "path": "",
        "opens": "here",
        "target": {
          "path": ""
        }
      },
      "asked": [],
      "assets": [],
      "counterparts": [
        "/view/"
      ]
    },
    "a file of a pinned revision": {
      "subject": {
        "kind": "file",
        "path": "docs/guide.md",
        "opens": "here",
        "target": {
          "path": "g1-ZG9jcw/g1-Z3VpZGUubWQ"
        }
      },
      "asked": [],
      "assets": [],
      "counterparts": [
        "/view/g1-ZG9jcw/g1-Z3VpZGUubWQ"
      ]
    },
    "a file, on a page with no GitHub repository": {
      "subject": {
        "kind": "file",
        "path": "README.md",
        "opens": "here",
        "target": {
          "path": "README.md"
        }
      },
      "asked": [],
      "assets": [],
      "counterparts": []
    },
    "the pull request list": {
      "subject": {
        "kind": "pulls"
      },
      "asked": [],
      "assets": [
        "pull-request-list"
      ],
      "counterparts": []
    }
  },
  "a commit's card and prefetch together": {
    "subject": {
      "kind": "commit",
      "revision": "837bda622f37d716397d71eac1ca8abb7263e01f"
    },
    "summary": {
      "title": "Start the demo",
      "detail": "Ada Author · 6d ago"
    },
    "asked": [
      "GET /api/git/commit/837bda622f37d716397d71eac1ca8abb7263e01f",
      "GET /api/plugin/diff/comparison?revision=837bda622f37d716397d71eac1ca8abb7263e01f"
    ],
    "assets": [
      "diff"
    ]
  },
  "requests": [
    "GET /api/plugin/github/pulls?q=12",
    "GET /api/plugin/github/pulls?q=13",
    "GET /api/plugin/github/pulls?q=14",
    "GET /api/plugin/github/pulls?q=15",
    "GET /api/plugin/github/pulls?q=99",
    "GET /api/plugin/github/stacks",
    "GET /api/plugin/github/stacks",
    "GET /api/git/commit/5ed518dc01e604da80e752ddd5ee4de4b6e14bd1",
    "GET /api/git/commit/0123456789abcdef0123456789abcdef01234567",
    "GET /api/plugin/github/pull?number=12&warm=1",
    "GET /api/plugin/diff/comparison?revision=5ed518dc01e604da80e752ddd5ee4de4b6e14bd1",
    "GET /api/git/commit/837bda622f37d716397d71eac1ca8abb7263e01f",
    "GET /api/plugin/diff/comparison?revision=837bda622f37d716397d71eac1ca8abb7263e01f"
  ],
  "aborted": []
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
