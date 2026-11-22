- Two servers started at the same moment on one port no longer both announce it.
  Each `metab` now holds its port from the moment it chooses it, so the second takes the
  next port, where before one exited with “address already in use” after printing a
  `Serving` line whose address the other server then answered with its own folder.
  A connection made while a server is still starting now waits for its answer instead of
  being refused.
