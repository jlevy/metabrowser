- A stack page’s rendered diff reads the stack once per file, not twice, and the time a
  request spends deciding whether its snapshot is still served is recorded as the
  `admit` Server-Timing phase.
