-- Initialize test database for integration tests
-- This script runs automatically when PostgreSQL container starts

-- Create test database
CREATE DATABASE claude_bot_test;

-- Connect to test database
\c claude_bot_test;

-- Grant permissions to postgres user (default)
GRANT ALL PRIVILEGES ON DATABASE claude_bot_test TO postgres;

-- Grant schema permissions
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
