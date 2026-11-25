---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
patterns:
  STORE: '[0-9a-f]{16}'
---
# Golden Test: View File and View on Branch From a Diff

Each file bar of a diff offers one control, for the side of the change that is a file at
a commit: the change’s new side.
A deleted file has none, a renamed file opens at its new path, and a submodule or a
symbolic link has none, since a submodule has no file to show and a link would open its
target rather than the link text the diff shows.
The old side has no place in the main UI: a commit’s parent is a bare commit, and a pull
request’s is the merge base, which no branch is at.

On a commit’s diff the control is **View file**. At the commit the page shows it is a
link to the file’s `/view/` address, which the browser follows as it follows any link.
At another commit the file has no address until the server serves that commit, so it is
a button: it sends `POST /api/source/pin` with the commit and the address, and the page
goes where the answer says.
A switch the server does not make says why under the bar, and the page stays.
One switch runs at a time, and a page that is leaving after one asks nothing more until
the browser brings it back; a diff unmounted before the answer goes nowhere.

On a pull request’s Changes the control is **View on branch**, offered only while the
diff shows the pull request’s head, which the pull request’s page names with its head
ref. On a mirror it follows the same rule, and a switch names that ref (`under`) beside
the commit, so the page lands on the pull request’s code as Browse code lands on it.
When the pull request moved on after the page was drawn, that ref is at another commit,
and the server switches nothing (`409 ref_moved`); the page says the head moved.
A diff of another commit than the head has none.
Beside a checkout the page has no pin: the control is a link to the working-tree file
while the checkout’s HEAD is the diff’s head, mapped into the served folder when that is
a folder inside the checkout, and absent otherwise.
When the page learns that another tab switched the server’s pin, each link, which would
now open the same path at that other pin, becomes the switch back.

This browserless session loads the production `builtin_plugins/diff/index.js` with its
modules and `static/navigation.js`, and plays the server’s side from
`tests/fixtures/diff-view-file-responses.json`: the documents, the block the shell
writes into a page, and the pin route’s answers, as the in-process application gave them
while it served the mirror of `tests/diff_view_file_fixture.py` with pull request 7’s
head ref, and then while a server on another repository, and one on a folder, answered a
page left open from it.
`tests/test_diff_view_file_session.py` replays that story and fails when the recording
drifts. The plugin-data transport, syntax highlighting, and preferences are stand-ins,
and the page is an element tree that records what the production code builds.
The stand-in for the pin route refuses a request whose content type is not JSON, as the
server does, and each request line shows the type it was sent with.

Each bar lists its controls as `[label] link <address>` or
`[label] button[type=button]`, then what following it does, which is also its tooltip
and accessible name.
`latin1-�.txt` is a name that is not UTF-8: its address on a pin carries the name’s
bytes, and a checkout’s folder has no address for it.
`opens` is the path an address names, by the production decoder, `busy` lists the
controls marked `aria-busy`, and a refusal is shown with the role it is announced by.
`modules` lists the plugin modules a step loaded, which a browser requests once each
from `/plugin-static/diff/`: a served folder’s diff comes first, and the first diff on a
pin is what loads `diff-view-file.js`, while its comparison is still on its way.
The last steps have the server not answer for that module.
`failure` is what the view announces in place of a diff, and `logged` is what it writes
to the console, which names the request that failed.

```console
$ node tests/dom/diff-view-file-session.js
{
  "steps": [
    {
      "step": "a served folder's page has no controls",
      "requests": [],
      "modules": [
        "diff-fold.js",
        "diff-intraline.js",
        "diff-model.js",
        "diff-render-model.js",
        "diff-syntax.js",
        "diff-view.js",
        "index.js"
      ],
      "bars": {
        "M README.md": [],
        "A added.txt": [],
        "D gone.txt": [],
        "M latin1-�.txt": [],
        "M link": [],
        "R100 src/old_name.py → src/new_name.py": [],
        "M vendor/lib": []
      }
    },
    {
      "step": "a pin's first diff asks for the module before its comparison answers",
      "requests": [],
      "modules": [
        "diff-view-file.js"
      ],
      "bars": {}
    },
    {
      "step": "a commit's diff on the page that shows that commit has one View file a file",
      "requests": [],
      "bars": {
        "M README.md": [
          "[View file] link /view/g1-UkVBRE1FLm1k · Open README.md at 6ac4c8b, the commit this page shows"
        ],
        "A added.txt": [
          "[View file] link /view/g1-YWRkZWQudHh0 · Open added.txt at 6ac4c8b, the commit this page shows"
        ],
        "D gone.txt": [],
        "M latin1-�.txt": [
          "[View file] link /view/g1-bGF0aW4xLekudHh0 · Open latin1-�.txt at 6ac4c8b, the commit this page shows"
        ],
        "M link": [],
        "R100 src/old_name.py → src/new_name.py": [
          "[View file] link /view/g1-c3Jj/g1-bmV3X25hbWUucHk · Open src/new_name.py at 6ac4c8b, the commit this page shows"
        ],
        "M vendor/lib": []
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
      "step": "the same diff from the page on the parent switches to the commit",
      "requests": [],
      "bars": {
        "M README.md": [
          "[View file] button[type=button] · Switch to 6ac4c8b and open README.md"
        ],
        "A added.txt": [
          "[View file] button[type=button] · Switch to 6ac4c8b and open added.txt"
        ],
        "D gone.txt": [],
        "M latin1-�.txt": [
          "[View file] button[type=button] · Switch to 6ac4c8b and open latin1-�.txt"
        ],
        "M link": [],
        "R100 src/old_name.py → src/new_name.py": [
          "[View file] button[type=button] · Switch to 6ac4c8b and open src/new_name.py"
        ],
        "M vendor/lib": []
      }
    },
    {
      "step": "View file asks the server to switch",
      "requests": [
        "POST /api/source/pin [content-type: application/json] {\"oid\":\"6ac4c8b5eb94eecbdb621d629b31066f050c75f1\",\"view\":\"/view/g1-c3Jj/g1-bmV3X25hbWUucHk\"}"
      ],
      "busy": [
        "R100 src/old_name.py → src/new_name.py [View file]"
      ],
      "barStillOpen": true
    },
    {
      "step": "a second switch waits for the first",
      "requests": [],
      "busy": [
        "R100 src/old_name.py → src/new_name.py [View file]"
      ]
    },
    {
      "step": "the page goes where the server says, and the server is on its branch again",
      "requests": [],
      "opens": "src/new_name.py",
      "served": "refs/remotes/origin/trunk",
      "busy": [
        "R100 src/old_name.py → src/new_name.py [View file]"
      ],
      "navigated": [
        "/view/g1-c3Jj/g1-bmV3X25hbWUucHk"
      ]
    },
    {
      "step": "a page that is leaving asks nothing more",
      "requests": [],
      "busy": [
        "R100 src/old_name.py → src/new_name.py [View file]"
      ]
    },
    {
      "step": "a pageshow that restores nothing changes nothing",
      "requests": [],
      "busy": [
        "R100 src/old_name.py → src/new_name.py [View file]"
      ]
    },
    {
      "step": "a page the browser brings back switches again",
      "requests": [
        "POST /api/source/pin [content-type: application/json] {\"oid\":\"6ac4c8b5eb94eecbdb621d629b31066f050c75f1\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "busy": [
        "M README.md [View file]"
      ]
    },
    {
      "step": "a diff unmounted before the answer goes nowhere",
      "requests": [],
      "pageshowListeners": 1
    },
    {
      "step": "a root commit's diff opens at its own commit",
      "requests": [],
      "bars": {
        "A README.md": [
          "[View file] button[type=button] · Switch to a5232ab and open README.md"
        ],
        "A changes.patch": [
          "[View file] button[type=button] · Switch to a5232ab and open changes.patch"
        ],
        "A docs/guide.md": [
          "[View file] button[type=button] · Switch to a5232ab and open docs/guide.md"
        ],
        "A gone.txt": [
          "[View file] button[type=button] · Switch to a5232ab and open gone.txt"
        ],
        "A kept.txt": [
          "[View file] button[type=button] · Switch to a5232ab and open kept.txt"
        ],
        "A latin1-�.txt": [
          "[View file] button[type=button] · Switch to a5232ab and open latin1-�.txt"
        ],
        "A link": [],
        "A src/old_name.py": [
          "[View file] button[type=button] · Switch to a5232ab and open src/old_name.py"
        ],
        "A vendor/lib": []
      }
    },
    {
      "step": "a pull request's Changes at its head has one View on branch a file, a link",
      "requests": [
        "GET /api/plugin/github/pull-comparison?number=7&left=a5232ab93056074aa3dd87c7b3c28ca84081a6a0&right=6ac4c8b5eb94eecbdb621d629b31066f050c75f1&base_policy=merge_base&store=0123456789abcdef"
      ],
      "bars": {
        "M README.md": [
          "[View on branch] link /view/g1-UkVBRE1FLm1k · Open README.md at 6ac4c8b, the commit this page shows"
        ],
        "A added.txt": [
          "[View on branch] link /view/g1-YWRkZWQudHh0 · Open added.txt at 6ac4c8b, the commit this page shows"
        ],
        "D gone.txt": [],
        "M latin1-�.txt": [
          "[View on branch] link /view/g1-bGF0aW4xLekudHh0 · Open latin1-�.txt at 6ac4c8b, the commit this page shows"
        ],
        "M link": [],
        "R100 src/old_name.py → src/new_name.py": [
          "[View on branch] link /view/g1-c3Jj/g1-bmV3X25hbWUucHk · Open src/new_name.py at 6ac4c8b, the commit this page shows"
        ],
        "M vendor/lib": []
      }
    },
    {
      "step": "View on branch at the head is a link the browser follows",
      "requests": [],
      "prevented": false,
      "follows": "/view/g1-UkVBRE1FLm1k"
    },
    {
      "step": "on a page at another commit, View on branch switches to the head",
      "requests": [
        "GET /api/plugin/github/pull-comparison?number=7&left=a5232ab93056074aa3dd87c7b3c28ca84081a6a0&right=6ac4c8b5eb94eecbdb621d629b31066f050c75f1&base_policy=merge_base&store=0123456789abcdef"
      ],
      "bars": {
        "M README.md": [
          "[View on branch] button[type=button] · Switch to 6ac4c8b, this pull request's head, and open README.md"
        ],
        "A added.txt": [
          "[View on branch] button[type=button] · Switch to 6ac4c8b, this pull request's head, and open added.txt"
        ],
        "D gone.txt": [],
        "M latin1-�.txt": [
          "[View on branch] button[type=button] · Switch to 6ac4c8b, this pull request's head, and open latin1-�.txt"
        ],
        "M link": [],
        "R100 src/old_name.py → src/new_name.py": [
          "[View on branch] button[type=button] · Switch to 6ac4c8b, this pull request's head, and open src/new_name.py"
        ],
        "M vendor/lib": []
      }
    },
    {
      "step": "the switch names the pull request's ref, which the server then serves",
      "requests": [
        "POST /api/source/pin [content-type: application/json] {\"oid\":\"6ac4c8b5eb94eecbdb621d629b31066f050c75f1\",\"under\":\"refs/pull/7/head\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "opens": "README.md",
      "served": "refs/pull/7/head",
      "navigated": [
        "/view/g1-UkVBRE1FLm1k"
      ]
    },
    {
      "step": "a pull request whose head moved since the page was drawn switches nothing",
      "requests": [
        "GET /api/plugin/github/pull-comparison?number=7&left=a5232ab93056074aa3dd87c7b3c28ca84081a6a0&right=6ac4c8b5eb94eecbdb621d629b31066f050c75f1&base_policy=merge_base&store=0123456789abcdef",
        "POST /api/source/pin [content-type: application/json] {\"oid\":\"6ac4c8b5eb94eecbdb621d629b31066f050c75f1\",\"under\":\"refs/pull/7/head\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "busy": [],
      "notices": {
        "M README.md": "[role=status] This pull request's head has moved; reload to see the newer changes."
      }
    },
    {
      "step": "a pull request's diff of another commit than its head has no controls",
      "requests": [
        "GET /api/plugin/github/pull-comparison?number=7&left=a5232ab93056074aa3dd87c7b3c28ca84081a6a0&right=6ac4c8b5eb94eecbdb621d629b31066f050c75f1&base_policy=merge_base&store=0123456789abcdef"
      ],
      "bars": {
        "M README.md": [],
        "A added.txt": [],
        "D gone.txt": [],
        "M latin1-�.txt": [],
        "M link": [],
        "R100 src/old_name.py → src/new_name.py": [],
        "M vendor/lib": []
      }
    },
    {
      "step": "beside a checkout at the head, View on branch opens the working-tree file",
      "requests": [
        "GET /api/plugin/github/pull-comparison?number=7&left=a5232ab93056074aa3dd87c7b3c28ca84081a6a0&right=6ac4c8b5eb94eecbdb621d629b31066f050c75f1&base_policy=merge_base&store=0123456789abcdef"
      ],
      "bars": {
        "M README.md": [
          "[View on branch] link /view/README.md · Open your working-tree copy of README.md, in this checkout whose HEAD is this pull request's head"
        ],
        "A added.txt": [
          "[View on branch] link /view/added.txt · Open your working-tree copy of added.txt, in this checkout whose HEAD is this pull request's head"
        ],
        "D gone.txt": [],
        "M latin1-�.txt": [],
        "M link": [],
        "R100 src/old_name.py → src/new_name.py": [
          "[View on branch] link /view/src/new_name.py · Open your working-tree copy of src/new_name.py, in this checkout whose HEAD is this pull request's head"
        ],
        "M vendor/lib": []
      }
    },
    {
      "step": "a checkout served from a folder inside it opens only what is in that folder",
      "requests": [
        "GET /api/plugin/github/pull-comparison?number=7&left=a5232ab93056074aa3dd87c7b3c28ca84081a6a0&right=6ac4c8b5eb94eecbdb621d629b31066f050c75f1&base_policy=merge_base&store=0123456789abcdef"
      ],
      "bars": {
        "M README.md": [],
        "A added.txt": [],
        "D gone.txt": [],
        "M latin1-�.txt": [],
        "M link": [],
        "R100 src/old_name.py → src/new_name.py": [
          "[View on branch] link /view/new_name.py · Open your working-tree copy of src/new_name.py, in this checkout whose HEAD is this pull request's head"
        ],
        "M vendor/lib": []
      }
    },
    {
      "step": "a checkout whose HEAD is elsewhere has no controls",
      "requests": [
        "GET /api/plugin/github/pull-comparison?number=7&left=a5232ab93056074aa3dd87c7b3c28ca84081a6a0&right=6ac4c8b5eb94eecbdb621d629b31066f050c75f1&base_policy=merge_base&store=0123456789abcdef"
      ],
      "bars": {
        "M README.md": [],
        "A added.txt": [],
        "D gone.txt": [],
        "M latin1-�.txt": [],
        "M link": [],
        "R100 src/old_name.py → src/new_name.py": [],
        "M vendor/lib": []
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
        "POST /api/source/pin [content-type: application/json] {\"oid\":\"6ac4c8b5eb94eecbdb621d629b31066f050c75f1\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "busy": [],
      "notices": {
        "M README.md": "[role=status] This commit is still being fetched. Try again shortly."
      }
    },
    {
      "step": "asked again after the fetch, the origin does not have it",
      "requests": [
        "POST /api/source/pin [content-type: application/json] {\"oid\":\"6ac4c8b5eb94eecbdb621d629b31066f050c75f1\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "notices": {
        "M README.md": "[role=status] This commit is not on the origin."
      }
    },
    {
      "step": "a fetch that could not run says so",
      "requests": [
        "POST /api/source/pin [content-type: application/json] {\"oid\":\"6ac4c8b5eb94eecbdb621d629b31066f050c75f1\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "notices": {
        "M README.md": "[role=status] This commit could not be fetched. Try again."
      }
    },
    {
      "step": "a server that now serves a folder refuses",
      "requests": [
        "POST /api/source/pin [content-type: application/json] {\"oid\":\"6ac4c8b5eb94eecbdb621d629b31066f050c75f1\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "notices": {
        "M README.md": "[role=status] Could not open this commit. Try again."
      }
    },
    {
      "step": "a request that fails says so",
      "requests": [
        "POST /api/source/pin [content-type: application/json] {\"oid\":\"6ac4c8b5eb94eecbdb621d629b31066f050c75f1\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "notices": {
        "M README.md": "[role=status] The switch request failed."
      }
    },
    {
      "step": "asking again clears what the last refusal said",
      "requests": [
        "POST /api/source/pin [content-type: application/json] {\"oid\":\"6ac4c8b5eb94eecbdb621d629b31066f050c75f1\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "waiting": 1
    },
    {
      "step": "a pin another tab changed turns each link into the switch back",
      "requests": [
        "GET /api/plugin/github/pull-comparison?number=7&left=a5232ab93056074aa3dd87c7b3c28ca84081a6a0&right=6ac4c8b5eb94eecbdb621d629b31066f050c75f1&base_policy=merge_base&store=0123456789abcdef"
      ],
      "bars": {
        "M README.md": [
          "[View on branch] button[type=button] · Switch to 6ac4c8b, this pull request's head, and open README.md"
        ],
        "A added.txt": [
          "[View on branch] button[type=button] · Switch to 6ac4c8b, this pull request's head, and open added.txt"
        ],
        "D gone.txt": [],
        "M latin1-�.txt": [
          "[View on branch] button[type=button] · Switch to 6ac4c8b, this pull request's head, and open latin1-�.txt"
        ],
        "M link": [],
        "R100 src/old_name.py → src/new_name.py": [
          "[View on branch] button[type=button] · Switch to 6ac4c8b, this pull request's head, and open src/new_name.py"
        ],
        "M vendor/lib": []
      }
    },
    {
      "step": "and following it switches first",
      "requests": [
        "POST /api/source/pin [content-type: application/json] {\"oid\":\"6ac4c8b5eb94eecbdb621d629b31066f050c75f1\",\"under\":\"refs/pull/7/head\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "waiting": 1
    },
    {
      "step": "a page whose module does not load says so, and logs the request",
      "requests": [],
      "bars": {},
      "failure": [
        "Could not load this diff. Refresh the page to try again."
      ],
      "logged": [
        "metabrowser diff: view load failed · diff/view-file · Failed to fetch dynamically imported module"
      ]
    },
    {
      "step": "a diff that fails while the module fails too says the diff's failure",
      "requests": [],
      "bars": {},
      "failure": [
        "This commit's comparison failed."
      ],
      "logged": [
        "metabrowser diff: view load failed · diff/comparison · the comparison failed"
      ]
    },
    {
      "step": "a served folder's diff does not depend on the module",
      "requests": [],
      "bars": {
        "M README.md": [],
        "A added.txt": [],
        "D gone.txt": [],
        "M latin1-�.txt": [],
        "M link": [],
        "R100 src/old_name.py → src/new_name.py": [],
        "M vendor/lib": []
      },
      "failure": [],
      "logged": []
    }
  ]
}
? 0
```
