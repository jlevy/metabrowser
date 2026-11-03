// The second part of the Pulls panel's browserless session: what the panel says for each way a
// refresh can end and at its cap, a row whose text is markup, the list's own address, the page
// a selection opens, and the paint. The session is github-pulls-panel-session.js, run whole;
// this prints all but its steps, because tryscript matches a command's expected output as one
// regular expression and the whole transcript in one block is larger than V8 compiles.

process.argv.push("--part", "2");
require("./github-pulls-panel-session.js");
