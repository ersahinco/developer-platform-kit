-- Bootstrap SQL: loaded by PostgreSQL at container initialisation via docker-entrypoint-initdb.d
-- Enables pg_stat_statements so query performance can be observed during the migration example.

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
