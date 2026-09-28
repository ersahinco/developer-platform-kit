CREATE ROLE portal LOGIN PASSWORD 'ephemeral-test-only';
GRANT CONNECT, CREATE ON DATABASE portal TO portal;
