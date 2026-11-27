---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Pull Request’s Readiness on Its Page

An open pull request’s page says whether it can merge twice: the header’s badge, after
the state’s, and the Checks tab’s Merge status section, which opens the tab.
The server decides the verdict, its tone, its label, and each requirement’s status and
sentence (`pull_readiness.py`), and the page decides only where each row links.

`badge` is the header’s: the verdict’s tone and the server’s label, its accessible name
where auto-merge’s sentence adds to the label, and the link to the Checks tab.
`tip` is its tooltip, the requirements that are not met.
`sentence` is the Merge status section’s: the requirement that heads the verdict, or
none when nothing stands in the way.
`rows` are its rows, each its status’s word in that status’s tone, the server’s
sentence, and its link: Checks to the first failing or running check in the list below,
named by its place in that list, since two checks can share a name, Reviews that asked
for changes to the Conversation tab when it shows a review that did, and the rest to the
page the server names on GitHub; a met requirement links nowhere.
Auto-merge has a row of its own while it is on.
`checks` is the list below them, in `gh pr checks`’s order, a check a rule requires
marked `[Required]`.

`recorded` is pull request 7 as the page’s recording answers it
(`tests/fixtures/github-pull-page-responses.json`). The next four are the same pull
request as GitHub could have answered it, recorded as the server decides them by
`tests/test_github_pull_readiness_page.py`
(`tests/fixtures/github-pull-page-readiness.json`): merge conflicts with a required
check failing and changes requested, second in the merge queue, a status the Pulls tab’s
scan read, which counts the checks and lists none, so the page says the list is being
read and its Checks row links to GitHub, and every requirement met.
A merged pull request has no readiness.

`listed` is the recorded pull request once the list of pull requests says another state,
a second after its record’s update, which the header then shows, beside its record and
beside its core while the record is on its way.
The server judged the verdict with the pull request open, so only an open state draws
it: a page whose list learned of a merge, a close, or a draft first draws no verdict,
and so no Merge status section, until a read judges the state it shows.

```console
$ node tests/dom/github-pull-readiness-session.js
{
  "readiness": {
    "recorded": {
      "readiness": {
        "badge": "[attention: Checks pending] named \"Checks pending. Auto-merge enabled (squash).\" -> the checks tab",
        "tip": "Some checks are still pending: 2 successful, and 1 pending. Review required.",
        "sentence": "Some checks are still pending: 2 successful, and 1 pending.",
        "rows": [
          "[success: Met] conflicts: No merge conflicts with topic. -> no link",
          "[attention: Waiting] checks: Some checks are still pending: 2 successful, and 1 pending. -> View check -> the list's check 1, \"docs\"",
          "[attention: Waiting] reviews: Review required. -> View on GitHub https://github.com/octo/demo/pull/7",
          "auto-merge: Auto-merge enabled (squash)."
        ]
      },
      "checks": {
        "summary": "Some checks are still pending: 2 successful · 1 pending",
        "items": [
          "[pending: in progress] docs [Required] -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
          "[pass: success] tests (3.13) [Required] -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
          "[pass: success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
        ]
      }
    },
    "conflicts": {
      "readiness": {
        "badge": "[danger: Merge conflicts] -> the checks tab",
        "tip": "Merge conflicts with topic must be resolved. Some checks were not successful: 1 failing (1 required), and 2 successful. Changes requested.",
        "sentence": "Merge conflicts with topic must be resolved.",
        "rows": [
          "[danger: Unmet] conflicts: Merge conflicts with topic must be resolved. -> View on GitHub https://github.com/octo/demo/pull/7/conflicts",
          "[danger: Unmet] checks: Some checks were not successful: 1 failing (1 required), and 2 successful. -> View check -> the list's check 1, \"docs\"",
          "[danger: Unmet] reviews: Changes requested. -> View on GitHub https://github.com/octo/demo/pull/7"
        ]
      },
      "checks": {
        "summary": "Some checks were not successful: 1 failing · 2 successful",
        "items": [
          "[fail: failure] docs [Required] -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
          "[pass: success] tests (3.13) [Required] -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
          "[pass: success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
        ]
      }
    },
    "queued": {
      "readiness": {
        "badge": "[attention: Queued] -> the checks tab",
        "tip": "Queued to merge, position 2, in about 9 min.",
        "sentence": "Queued to merge, position 2, in about 9 min.",
        "rows": [
          "[attention: Waiting] queue: Queued to merge, position 2, in about 9 min. -> View on GitHub https://github.com/octo/demo/queue/topic",
          "[success: Met] conflicts: No merge conflicts with topic. -> no link",
          "[success: Met] checks: All checks were successful: 3 successful. -> no link",
          "[success: Met] reviews: Approved. -> no link"
        ]
      },
      "checks": {
        "summary": "All checks were successful: 3 successful",
        "items": [
          "[pass: success] tests (3.13) [Required] -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
          "[pass: success] docs [Required] -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
          "[pass: success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
        ]
      }
    },
    "listing": {
      "readiness": {
        "badge": "[attention: Checks pending] named \"Checks pending. Auto-merge enabled (squash).\" -> the checks tab",
        "tip": "Some checks are still pending: 2 successful, and 1 pending. Review required.",
        "sentence": "Some checks are still pending: 2 successful, and 1 pending.",
        "rows": [
          "[success: Met] conflicts: No merge conflicts with topic. -> no link",
          "[attention: Waiting] checks: Some checks are still pending: 2 successful, and 1 pending. -> View on GitHub https://github.com/octo/demo/pull/7/checks",
          "[attention: Waiting] reviews: Review required. -> View on GitHub https://github.com/octo/demo/pull/7",
          "auto-merge: Auto-merge enabled (squash)."
        ]
      },
      "checks": {
        "summary": "Some checks are still pending: 2 successful · 1 pending",
        "items": [],
        "listing": "the list is being read"
      }
    },
    "ready": {
      "readiness": {
        "badge": "[success: Ready to merge] -> the checks tab",
        "tip": null,
        "sentence": null,
        "rows": [
          "[success: Met] conflicts: No merge conflicts with topic. -> no link",
          "[success: Met] checks: All checks were successful: 3 successful. -> no link",
          "[success: Met] reviews: Approved. -> no link"
        ]
      },
      "checks": {
        "summary": "All checks were successful: 3 successful",
        "items": [
          "[pass: success] tests (3.13) [Required] -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
          "[pass: success] docs [Required] -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
          "[pass: success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
        ]
      }
    },
    "conflicts, with a review in the conversation that requested changes": [
      "[danger: Unmet] conflicts: Merge conflicts with topic must be resolved. -> View on GitHub https://github.com/octo/demo/pull/7/conflicts",
      "[danger: Unmet] checks: Some checks were not successful: 1 failing (1 required), and 2 successful. -> View check -> the list's check 1, \"docs\"",
      "[danger: Unmet] reviews: Changes requested. -> View in Conversation -> the conversation tab"
    ],
    "merged": null,
    "listed": {
      "the list says merged": {
        "record": "[Merged] no readiness",
        "core": "[Merged] no readiness"
      },
      "the list says draft": {
        "record": "[Draft] no readiness",
        "core": "[Draft] no readiness"
      },
      "the list says closed": {
        "record": "[Closed] no readiness",
        "core": "[Closed] no readiness"
      },
      "the list says open": {
        "record": "[Open] [attention: Checks pending] named \"Checks pending. Auto-merge enabled (squash).\" -> the checks tab",
        "core": "[Open] [attention: Checks pending] named \"Checks pending. Auto-merge enabled (squash).\" -> the checks tab"
      }
    }
  }
}
? 0
```
