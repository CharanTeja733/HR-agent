-- ============================================================================
-- HR Q&A Agent — Database Initialization Script (reference)
-- ============================================================================
-- This script is provided for manual database setup.
-- In production the same DDL is executed by ``backend.app.database.create_tables()``
-- on application startup.
-- ============================================================================

-- 1. Enable the pgvector extension -------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Tables ------------------------------------------------------------------

-- users
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            VARCHAR(50)  NOT NULL DEFAULT 'employee'
                    CHECK (role IN ('employee', 'manager', 'hr_admin')),
    department      VARCHAR(100) NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- sessions
CREATE TABLE IF NOT EXISTS sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id),
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    device_info JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours')
);

-- messages
CREATE TABLE IF NOT EXISTS messages (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     UUID         NOT NULL REFERENCES sessions(id),
    user_id        UUID         NOT NULL REFERENCES users(id),
    role           VARCHAR(20)  NOT NULL
                   CHECK (role IN ('user', 'assistant')),
    content        TEXT         NOT NULL,
    sources        JSONB,
    confidence     VARCHAR(20)
                   CHECK (confidence IN ('high', 'medium', 'low', 'none')),
    tokens_used    INTEGER,
    classification VARCHAR(30),
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- feedback
CREATE TABLE IF NOT EXISTS feedback (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID        NOT NULL REFERENCES messages(id),
    user_id    UUID        NOT NULL REFERENCES users(id),
    rating     VARCHAR(10) NOT NULL
               CHECK (rating IN ('positive', 'negative')),
    reason     VARCHAR(50),
    comment    TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- hr_documents
CREATE TABLE IF NOT EXISTS hr_documents (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content      TEXT          NOT NULL,
    embedding    VECTOR(768)   NOT NULL,
    source       VARCHAR(500)  NOT NULL,
    page         INTEGER,
    section      VARCHAR(500),
    chunk_index  INTEGER       NOT NULL,
    access_level VARCHAR(50)   NOT NULL DEFAULT 'all'
                 CHECK (access_level IN ('all', 'manager', 'hr_admin')),
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Indexes -----------------------------------------------------------------

-- users
CREATE INDEX IF NOT EXISTS idx_users_role       ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_department ON users(department);

-- sessions
CREATE INDEX IF NOT EXISTS idx_sessions_user_id     ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_last_active ON sessions(last_active);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at  ON sessions(expires_at);

-- messages
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id    ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- feedback
CREATE INDEX IF NOT EXISTS idx_feedback_message_id ON feedback(message_id);
CREATE INDEX IF NOT EXISTS idx_feedback_user_id    ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating     ON feedback(rating);

-- hr_documents
CREATE INDEX IF NOT EXISTS idx_hr_documents_source       ON hr_documents(source);
CREATE INDEX IF NOT EXISTS idx_hr_documents_access_level ON hr_documents(access_level);

-- vector index (ivfflat — requires pgvector extension to be loaded)
CREATE INDEX IF NOT EXISTS idx_hr_documents_embedding
ON hr_documents
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 4. Seed data (reference — executed by backend/app/seed.py on startup) -------
/*
INSERT INTO users (email, hashed_password, full_name, role, department) VALUES
    ('admin@company.com', '$2b$...', 'Admin User',    'hr_admin', 'hr'),
    ('john@company.com',  '$2b$...', 'John Doe',      'employee', 'engineering'),
    ('sarah@company.com', '$2b$...', 'Sarah Smith',   'manager',  'sales'),
    ('priya@company.com', '$2b$...', 'Priya Sharma',  'employee', 'hr');
*/
