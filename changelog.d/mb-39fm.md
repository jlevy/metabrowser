- **The eyebrow’s served root is a link.** Above a file or folder, the served root’s
  whole address, such as `~/wrk/project`, is now one link that opens the root, where it
  was dimmed text with a separate `/` after it as the only link.
  Each folder under the root is its own link, as before, every link is followed by a `/`
  that is plain text, and the address ends in a slash: `~/wrk/project / docs /`. The
  directories above the served root are not links, because nothing above the root is
  open, and a long root is still cut from its start
  ([View Headers](docs/design-system.md#view-headers)).
