- Opening a pull request whose prefetch was just being stopped to let other work go no
  longer leaves it unrefreshed, on a mirror and in a repository folder alike: the
  request was answered as joining that work, which then ended without fetching, and now
  the pull request’s refresh starts again as the reader’s own.
  In a folder the same holds for the optional comparison a Conversation page starts,
  when a request for another pull request has just ended it.
