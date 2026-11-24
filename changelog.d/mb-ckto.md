- A first clone from GitHub is refused only when it would not fit on the cache’s volume
  with `METABROWSER_CACHE_RESERVE_MB`, 1 GB by default, still free, in place of a fixed
  1,350,000 KB size limit; `METABROWSER_MAX_FIRST_CLONE_KB` is gone.
  Any first clone, from any host, is refused while the volume has less than the reserve
  free. The refusal names the volume’s free space, the reserve, and the repository’s size
  where GitHub reports one, and `metab --doctor` warns when the volume has less free
  than the reserve. See
  [large repositories](docs/reviewing-pull-requests.md#large-repositories).
