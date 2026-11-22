- Fixed Load more in a Source view for files with CRLF or lone CR line endings.
  The text it appended kept the file’s own line endings while the first part had them
  normalized, so the appended part of a file with lone CRs showed as one line with no
  line numbers, a copy of the view had mixed line endings, and a CRLF that fell across
  the boundary between two loaded parts showed as an extra empty line.
  The first render and every appended part now go through one normalization.
