- Opening a pull request whose prefetch was just being stopped to let other work go no
  longer leaves it unrefreshed: the request was answered as joining that work, which
  then ended without fetching, and now the pull request’s refresh starts again as the
  reader’s own.
