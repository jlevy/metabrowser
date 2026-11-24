- Opening a repository whose branches or tags differ only in letter case, on a
  case-insensitive filesystem such as macOS’s default, again refuses it with
  `ref_case_collision`, naming the refs, with Git 2.56.1. That Git refuses the second
  ref of such a pair and exits with an error, which Metabrowser reported as “the fetch
  into staging failed”; Git 2.50.1 keeps one ref under both names and succeeds, which
  was already refused.
