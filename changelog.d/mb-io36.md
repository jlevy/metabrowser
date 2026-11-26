- An open pull request’s page says whether it can merge, in GitHub’s words: a badge
  after its state, such as **Merge conflicts**, **Checks pending**, or **Ready to
  merge**, green, yellow, or red as GitHub’s CLI colors it, whose tooltip lists what
  stands in the way and which opens **Checks**. The badge keeps one width whatever it
  says, so nothing in its row moves as checks finish, and in a narrow pane it is the
  verdict’s icon alone, so the dates beside it keep their room
  ([A Pull Request’s Readiness](docs/design-system.md#a-pull-requests-readiness)).

- The **Checks** tab opens with **Merge status**: the verdict, then a row for each thing
  GitHub weighs, conflicts, checks, reviews, being up to date, the base branch’s rules,
  and the merge queue, each met, waiting, unmet, or unknown and linked to where to act
  on it, and a row while auto-merge is on.
  It replaces the conflicts sentence that ended the tab
  ([Reviewing Pull Requests](docs/reviewing-pull-requests.md#tabs)).

- A check a rule on the base branch requires is marked **Required**, and pending checks
  are the same yellow as everything else that waits.
  Before the page has read a pull request’s list of checks itself, as after the Pulls
  tab counted them, **Checks** shows GitHub’s summary and says the list is being read.
