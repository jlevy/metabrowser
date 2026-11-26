- A stack’s page no longer says “This stack has changed since its comparison was drawn”
  a few seconds after it opens, with a Show the new comparison that seemed to do
  nothing. Until you scroll, click, press a key, or open a tab or a file, the page draws
  each newer comparison itself, since a stack whose pull requests’ records arrive one by
  one is catching up, not changing; and a new comparison with the same two commits and
  the same files changes nothing on the page.
  After that, one that would look different is offered with what changed, such as “#845
  has 2 new commits, #843 was merged, and #848 joined the stack.”, and Show the new
  comparison draws it and clears the notice
  ([A New Comparison](docs/design-system.md#a-new-comparison)).

- `GET /api/plugin/github/stack` takes `since`, the key of a comparison it answered
  before, keeps that comparison while a page asks, and answers `moved`: for each member
  whose head moved since, the commits its new head adds that the comparison did not
  show, or `null` when its branch was rewritten
  ([The Stack Page](docs/project/architecture/arch-github-pull-requests.md#the-stack-page)).
