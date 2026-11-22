-- The database the SQLite table goldens and tests read: every shape the plan's Testing
-- Strategy names, built by tests/sqlite_fixture.py from this text.

-- A rowid table keyed by its integer primary key, with an index, typed and mistyped
-- values, nulls in an indexed column, and values past what a page reads whole.
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT,
  age INTEGER,
  active BOOLEAN,
  joined DATE,
  prefs JSON,
  avatar BLOB,
  bio TEXT
);
CREATE INDEX users_email ON users(email);
INSERT INTO users VALUES
  (1, 'Ada', 'ada@example.com', 36, 1, '2020-01-02', '{"theme":"dark"}', x'00ff10', NULL),
  (2, 'Bob', NULL, 'unknown', 0, '2021-03-04', 'not json', NULL, ''),
  (3, 'Cy', 'cy@example.com', 9007199254740993, 1, NULL, '[1,2]', NULL, hex(zeroblob(2600))),
  (4, 'Dee', NULL, -9223372036854775808, 2, '2019-12-31', NULL, zeroblob(300), NULL),
  (5, 'Eve', 'EVE@example.com', 41, 1, 20230101, NULL, NULL, CAST(x'ff41' AS TEXT)),
  (6, 'Fay', 7, 29, 0, '2018-05-06', NULL, NULL, NULL);

-- A rowid table with no integer primary key, so its key is the hidden rowid, and a
-- foreign key to users, one of whose values names no user.
CREATE TABLE orders (
  user_id INTEGER REFERENCES users(id),
  total REAL,
  note TEXT
);
INSERT INTO orders VALUES
  (1, 9.5, 'first'),
  (1, 1e999, NULL),
  (2, -1e999, 'second'),
  (99, 0.5, 'dangling'),
  (NULL, NULL, 'no user');

-- A WITHOUT ROWID table with a composite primary key, and a table whose composite
-- foreign key names it.
CREATE TABLE tags (
  owner INTEGER NOT NULL,
  tag TEXT NOT NULL COLLATE NOCASE,
  PRIMARY KEY (owner, tag)
) WITHOUT ROWID;
INSERT INTO tags VALUES (1, 'admin'), (1, 'beta'), (3, 'beta');
CREATE TABLE grants (
  id INTEGER PRIMARY KEY,
  owner INTEGER,
  tag TEXT,
  FOREIGN KEY (owner, tag) REFERENCES tags(owner, tag)
);
INSERT INTO grants VALUES (1, 1, 'ADMIN'), (2, 3, 'beta'), (3, 2, 'gamma');

-- A table keyed by blobs, and one whose columns shadow every rowid alias.
CREATE TABLE blobs (k BLOB PRIMARY KEY, v TEXT) WITHOUT ROWID;
INSERT INTO blobs VALUES (x'01', 'one'), (x'0203', 'two'), (x'04', hex(zeroblob(3000)));
CREATE TABLE shadows (rowid TEXT, _rowid_ TEXT, oid TEXT);
INSERT INTO shadows VALUES ('a', 'b', 'c'), ('d', 'e', 'f');

-- A value past the reader's length limit, which only blobopen reads.
CREATE TABLE huge (id INTEGER PRIMARY KEY, body TEXT);
INSERT INTO huge VALUES (1, 'small'), (2, hex(zeroblob(600000)));

-- A STRICT table, generated columns, and a view that calls built-in functions.
CREATE TABLE prices (
  item TEXT PRIMARY KEY,
  cents INTEGER NOT NULL,
  dollars REAL GENERATED ALWAYS AS (cents / 100.0) VIRTUAL,
  label TEXT GENERATED ALWAYS AS (upper(item)) STORED
) STRICT;
INSERT INTO prices (item, cents) VALUES ('tea', 250), ('cake', 400);
CREATE VIEW shouting AS SELECT upper(name) AS name, length(name) AS letters FROM users;

-- Names a path segment cannot carry as they are.
CREATE TABLE "order items" (id INTEGER PRIMARY KEY, what TEXT);
INSERT INTO "order items" VALUES (1, 'spaced');
CREATE TABLE "g1-like" (id INTEGER PRIMARY KEY);
CREATE TABLE "~tilde" (id INTEGER PRIMARY KEY);

-- A virtual table, its shadow tables, and an internal table.
CREATE VIRTUAL TABLE notes USING fts5(body);
INSERT INTO notes VALUES ('remember the milk');
CREATE TABLE counters (id INTEGER PRIMARY KEY AUTOINCREMENT, n INTEGER);
INSERT INTO counters (n) VALUES (1), (2);
