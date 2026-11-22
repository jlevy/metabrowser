-- A table past the row count an unindexed sort may read
-- (SORT_UNINDEXED_MAX_ROWS in builtin_plugins/sqlite/reader.py): its indexed field
-- sorts, and its other fields say why they do not.
CREATE TABLE events (id INTEGER PRIMARY KEY, at INTEGER, kind TEXT);
CREATE INDEX events_at ON events(at);
WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n LIMIT 100001)
INSERT INTO events SELECT i, CASE WHEN i % 10 = 0 THEN NULL ELSE i % 997 END, 'k' || (i % 7) FROM n;
