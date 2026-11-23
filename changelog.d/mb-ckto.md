- A first clone from GitHub is refused only when it would not fit on the cache’s volume
  with `METABROWSER_CACHE_RESERVE_MB`, 1 GB by default, still free, in place of a fixed
  1,350,000 KB size limit; `METABROWSER_MAX_FIRST_CLONE_KB` is gone.
  The refusal names the repository’s size, the volume’s free space, and the reserve, and
  `metab --doctor` warns when the volume has less free than the reserve.
  See [large repositories](docs/reviewing-pull-requests.md#large-repositories).
