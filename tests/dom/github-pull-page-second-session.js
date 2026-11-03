// The second part of the pull-request page's browserless session: what Files changed
// says when the comparison is unavailable, the review comments' hunks, and the reader's
// place. The session is github-pull-page-session.js, run whole; this prints its second
// half, because tryscript matches a command's expected output as one regular expression
// and the whole transcript in one block is larger than V8 compiles.

process.argv.push("--part", "2");
require("./github-pull-page-session.js");
