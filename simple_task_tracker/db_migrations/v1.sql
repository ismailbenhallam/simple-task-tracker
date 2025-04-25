CREATE TABLE IF NOT EXISTS tasks
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT      NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at   TIMESTAMP,
    date       DATE      NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks (date);
CREATE INDEX IF NOT EXISTS idx_tasks_name_date ON tasks (name, date);