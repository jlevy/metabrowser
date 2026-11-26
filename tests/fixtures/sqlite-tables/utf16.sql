-- A database stored in UTF-16: a long text is previewed from its stored bytes.
PRAGMA encoding = 'UTF-16le';
CREATE TABLE words (id INTEGER PRIMARY KEY, word TEXT);
INSERT INTO words VALUES (1, 'héllo wörld'), (2, 'é' || hex(zeroblob(2600)));
