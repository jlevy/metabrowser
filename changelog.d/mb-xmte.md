- An untrusted Markdown document is no longer refused as “The document renderer could
  not start” when the renderer is only slow to start on a heavily loaded machine.
  A render waited 5 seconds for the renderer’s process, the render deadline’s default,
  and a cold start takes 2.7 to 6.8 seconds at a load average near 360. The wait is now
  its own measured bound (`_START_WAIT_S` in
  `src/metabrowser/diff/markdown_projection_worker.py`), and
  `METABROWSER_INERT_RENDER_DEADLINE_MS` still bounds only the render itself.
