- In a repository folder, opening a pull request whose prefetch was waiting behind
  another pull request’s prefetch now stops that other prefetch, as a mirror does: the
  opened pull request’s refresh waited for the other one to finish, not to unwind.
