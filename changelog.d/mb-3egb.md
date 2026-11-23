- Opening a pull request whose prefetch was waiting behind another pull request’s
  prefetch now stops that other prefetch, on a mirror and in a repository folder alike:
  the opened pull request’s refresh waited for the other one to finish, not to unwind.
