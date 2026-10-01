---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: View File From a Diff

On a page that shows a pinned revision, each file bar of a diff offers the file at the
sides of the change that exist: **View file** at the new side, and **View at parent** (a
commit’s diff) or **View at base** (a comparison from a merge base, as a pull request’s
Files changed is) at the old side.
A deleted file has only its old side, an added file only its new side, and a renamed
file’s old side is its old path.

A side at the commit the page shows is a link to the file’s `/view/` address, which the
browser follows as it follows any link.
A side at another commit has no address until the server serves that commit, so it is a
button: it sends `POST /api/source/pin` with the commit and the address, and the page
goes where the answer says.
A switch the server does not make says why under the bar, and the page stays.

This browserless session loads the production `builtin_plugins/diff/index.js` with its
modules and `static/navigation.js`, and plays the server’s side from
`tests/fixtures/diff-view-file-responses.json`: the documents, the block the shell
writes into a page, and the pin route’s answers, as the in-process application gave them
while it served the mirror of `tests/diff_view_file_fixture.py`, and then while a server
on another repository, and one on a folder, answered a page left open from it.
`tests/test_diff_view_file_session.py` replays that story and fails when the recording
drifts. The plugin-data transport, syntax highlighting, and preferences are stand-ins,
and the page is an element tree that records what the production code builds.

Each bar lists its controls as `[label] link <address>` or `[label] button`, then what
following it does, which is also its tooltip and accessible name.
`latin1-�.txt` is a name that is not UTF-8: its address carries the name’s bytes.
`opens` is the path an address names, by the production decoder.

```console
$ node tests/dom/diff-view-file-session.js
{
  "steps": [
    {
      "step": "a commit's diff on the page that shows that commit",
      "requests": [],
      "bars": {
        "M README.md": [
          "[View at parent] button · Switch to fb85257e8b12 and open README.md",
          "[View file] link /view/g1-UkVBRE1FLm1k · Open README.md at 037ec682a66f, the commit this page shows"
        ],
        "A added.txt": [
          "[View file] link /view/g1-YWRkZWQudHh0 · Open added.txt at 037ec682a66f, the commit this page shows"
        ],
        "D gone.txt": [
          "[View at parent] button · Switch to fb85257e8b12 and open gone.txt"
        ],
        "M latin1-�.txt": [
          "[View at parent] button · Switch to fb85257e8b12 and open latin1-�.txt",
          "[View file] link /view/g1-bGF0aW4xLekudHh0 · Open latin1-�.txt at 037ec682a66f, the commit this page shows"
        ],
        "R100 src/old_name.py → src/new_name.py": [
          "[View at parent] button · Switch to fb85257e8b12 and open src/old_name.py",
          "[View file] link /view/g1-c3Jj/g1-bmV3X25hbWUucHk · Open src/new_name.py at 037ec682a66f, the commit this page shows"
        ]
      }
    },
    {
      "step": "the link is the browser's to follow",
      "requests": [],
      "prevented": false,
      "follows": "/view/g1-UkVBRE1FLm1k",
      "opens": "README.md",
      "barStillOpen": true
    },
    {
      "step": "the rest of the bar still folds the file",
      "requests": [],
      "barStillOpen": false
    },
    {
      "step": "View at parent asks the server to switch",
      "requests": [
        "POST /api/source/pin {\"oid\":\"fb85257e8b1271d607ef49d7d4246fd2ad2484e6\",\"view\":\"/view/g1-c3Jj/g1-b2xkX25hbWUucHk\"}"
      ],
      "busy": "true",
      "barStillOpen": true
    },
    {
      "step": "a second switch waits for the first",
      "requests": []
    },
    {
      "step": "the page goes where the server says",
      "requests": [],
      "busy": "false",
      "opens": "src/old_name.py",
      "navigated": [
        "/view/g1-c3Jj/g1-b2xkX25hbWUucHk"
      ]
    },
    {
      "step": "the same diff from the page on the parent",
      "requests": [],
      "bars": {
        "M README.md": [
          "[View at parent] link /view/g1-UkVBRE1FLm1k · Open README.md at fb85257e8b12, the commit this page shows",
          "[View file] button · Switch to 037ec682a66f and open README.md"
        ],
        "A added.txt": [
          "[View file] button · Switch to 037ec682a66f and open added.txt"
        ],
        "D gone.txt": [
          "[View at parent] link /view/g1-Z29uZS50eHQ · Open gone.txt at fb85257e8b12, the commit this page shows"
        ],
        "M latin1-�.txt": [
          "[View at parent] link /view/g1-bGF0aW4xLekudHh0 · Open latin1-�.txt at fb85257e8b12, the commit this page shows",
          "[View file] button · Switch to 037ec682a66f and open latin1-�.txt"
        ],
        "R100 src/old_name.py → src/new_name.py": [
          "[View at parent] link /view/g1-c3Jj/g1-b2xkX25hbWUucHk · Open src/old_name.py at fb85257e8b12, the commit this page shows",
          "[View file] button · Switch to 037ec682a66f and open src/new_name.py"
        ]
      }
    },
    {
      "step": "View file switches to the commit",
      "requests": [
        "POST /api/source/pin {\"oid\":\"037ec682a66fd0c1b7a318237ecd6b386147a32d\",\"view\":\"/view/g1-c3Jj/g1-bmV3X25hbWUucHk\"}"
      ],
      "opens": "src/new_name.py",
      "navigated": [
        "/view/g1-c3Jj/g1-bmV3X25hbWUucHk"
      ]
    },
    {
      "step": "a root commit has only its own side",
      "requests": [],
      "bars": {
        "A README.md": [
          "[View file] button · Switch to fb85257e8b12 and open README.md"
        ],
        "A changes.patch": [
          "[View file] button · Switch to fb85257e8b12 and open changes.patch"
        ],
        "A docs/guide.md": [
          "[View file] button · Switch to fb85257e8b12 and open docs/guide.md"
        ],
        "A gone.txt": [
          "[View file] button · Switch to fb85257e8b12 and open gone.txt"
        ],
        "A kept.txt": [
          "[View file] button · Switch to fb85257e8b12 and open kept.txt"
        ],
        "A latin1-�.txt": [
          "[View file] button · Switch to fb85257e8b12 and open latin1-�.txt"
        ],
        "A src/old_name.py": [
          "[View file] button · Switch to fb85257e8b12 and open src/old_name.py"
        ]
      }
    },
    {
      "step": "a pull request's Files changed opens the merge base and the head",
      "requests": [
        "GET /api/plugin/diff/comparison?left=449e11d3cdd15a48bb472b9cc978995758946f5f&right=037ec682a66fd0c1b7a318237ecd6b386147a32d&base_policy=merge_base"
      ],
      "bars": {
        "M README.md": [
          "[View at base] button · Switch to fb85257e8b12 and open README.md",
          "[View file] link /view/g1-UkVBRE1FLm1k · Open README.md at 037ec682a66f, the commit this page shows"
        ],
        "A added.txt": [
          "[View file] link /view/g1-YWRkZWQudHh0 · Open added.txt at 037ec682a66f, the commit this page shows"
        ],
        "D gone.txt": [
          "[View at base] button · Switch to fb85257e8b12 and open gone.txt"
        ],
        "M latin1-�.txt": [
          "[View at base] button · Switch to fb85257e8b12 and open latin1-�.txt",
          "[View file] link /view/g1-bGF0aW4xLekudHh0 · Open latin1-�.txt at 037ec682a66f, the commit this page shows"
        ],
        "R100 src/old_name.py → src/new_name.py": [
          "[View at base] button · Switch to fb85257e8b12 and open src/old_name.py",
          "[View file] link /view/g1-c3Jj/g1-bmV3X25hbWUucHk · Open src/new_name.py at 037ec682a66f, the commit this page shows"
        ]
      }
    },
    {
      "step": "a patch file names no commit",
      "requests": [
        "GET /api/plugin/diff/document?path=g1-Y2hhbmdlcy5wYXRjaA"
      ],
      "opens": "changes.patch",
      "bars": {
        "M kept.txt": []
      }
    },
    {
      "step": "a commit the server's mirror lacks is being fetched",
      "requests": [
        "POST /api/source/pin {\"oid\":\"fb85257e8b1271d607ef49d7d4246fd2ad2484e6\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "notices": {
        "M README.md": "The mirror is fetching fb85257e8b12; try again when the fetch ends."
      }
    },
    {
      "step": "asked again after the fetch, the origin does not have it",
      "requests": [
        "POST /api/source/pin {\"oid\":\"fb85257e8b1271d607ef49d7d4246fd2ad2484e6\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "notices": {
        "M README.md": "Commit fb85257e8b12 is not in the mirror, and its origin does not have it."
      }
    },
    {
      "step": "a fetch that could not run says so",
      "requests": [
        "POST /api/source/pin {\"oid\":\"fb85257e8b1271d607ef49d7d4246fd2ad2484e6\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "notices": {
        "M README.md": "Commit fb85257e8b12 is not in the mirror, and fetching it failed."
      }
    },
    {
      "step": "a server that now serves a folder refuses",
      "requests": [
        "POST /api/source/pin {\"oid\":\"fb85257e8b1271d607ef49d7d4246fd2ad2484e6\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "notices": {
        "M README.md": "Could not switch to fb85257e8b12 (unsupported_for_subject)."
      }
    },
    {
      "step": "a request that fails says so",
      "requests": [
        "POST /api/source/pin {\"oid\":\"fb85257e8b1271d607ef49d7d4246fd2ad2484e6\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "notices": {
        "M README.md": "The switch request failed."
      }
    },
    {
      "step": "asking again clears what the last refusal said",
      "requests": [
        "POST /api/source/pin {\"oid\":\"fb85257e8b1271d607ef49d7d4246fd2ad2484e6\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "waiting": 1
    },
    {
      "step": "a served folder's page has no controls",
      "requests": [],
      "bars": {
        "M README.md": [],
        "A added.txt": [],
        "D gone.txt": [],
        "M latin1-�.txt": [],
        "R100 src/old_name.py → src/new_name.py": []
      }
    }
  ]
}
? 0
```
