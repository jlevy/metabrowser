- The branch chooser in the Files toolbar now shows the pull request a branch is the
  head of, on a second line of its row: its state’s icon, its number, and its title.
  A branch with several shows the open one first and counts the others, and a fork’s
  branch of the same name is not the repository’s branch, so it shows none.
  The filter box then finds a branch by its pull request as well as by its name, by `#`
  and the start of a number or by the words of a title.
  The pull requests are only what the cache already holds, so the list opens as fast as
  before and fills in while the cache does; a list of tags has none
  ([The Ref Selector](docs/design-system.md#the-ref-selector)). `GET /api/source/refs`
  carries them as `pulls` on a row and `pull_requests` on the envelope, and
  `PLUGIN_SDK_VERSION` is unchanged: the GitHub plugin publishes
  `mb.builtins.github.pullStateIcon` for the chooser.
