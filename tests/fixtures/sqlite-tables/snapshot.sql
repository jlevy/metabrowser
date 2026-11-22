-- A database marked as an fsqlite snapshot, whose reserved tables are internal.
PRAGMA application_id = 1179865420;
CREATE TABLE fsqlite_meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE applied_tx (id INTEGER PRIMARY KEY);
CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT);
INSERT INTO items VALUES (1, 'kept');
