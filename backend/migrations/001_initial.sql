PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS demo_sessions (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    profiles_revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student_profiles (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES demo_sessions(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    skills_json TEXT NOT NULL CHECK (json_valid(skills_json)),
    interests_json TEXT NOT NULL CHECK (json_valid(interests_json)),
    goals_json TEXT NOT NULL CHECK (json_valid(goals_json)),
    work_style_json TEXT NOT NULL CHECK (json_valid(work_style_json)),
    weekly_hours INTEGER CHECK (weekly_hours BETWEEN 0 AND 10),
    is_fictional INTEGER NOT NULL DEFAULT 1 CHECK (is_fictional = 1),
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE (id, session_id)
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES demo_sessions(id) ON DELETE CASCADE,
    client_request_id TEXT NOT NULL,
    title TEXT NOT NULL,
    idea TEXT NOT NULL,
    desired_team_size INTEGER NOT NULL CHECK (desired_team_size BETWEEN 2 AND 4),
    idea_revision INTEGER NOT NULL DEFAULT 1,
    requirements_json TEXT CHECK (requirements_json IS NULL OR json_valid(requirements_json)),
    requirements_source TEXT CHECK (requirements_source IN ('llm','fixture','template','manual')),
    requirements_revision INTEGER NOT NULL DEFAULT 0,
    confirmed_idea_revision INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (id, session_id),
    UNIQUE (session_id, client_request_id)
);

CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE (id, session_id),
    FOREIGN KEY (project_id, session_id) REFERENCES projects(id, session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_members (
    team_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    PRIMARY KEY (team_id, student_id),
    FOREIGN KEY (team_id, session_id) REFERENCES teams(id, session_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id, session_id) REFERENCES student_profiles(id, session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS roadmaps (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK (source IN ('llm','fixture','template','manual')),
    source_idea_revision INTEGER NOT NULL,
    source_requirements_revision INTEGER NOT NULL,
    source_team_revision INTEGER NOT NULL,
    source_profiles_revision INTEGER NOT NULL,
    assumptions_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(assumptions_json)),
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS milestones (
    id TEXT PRIMARY KEY,
    roadmap_id TEXT NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    week INTEGER NOT NULL CHECK (week BETWEEN 1 AND 4),
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    UNIQUE (roadmap_id, week)
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    milestone_id TEXT NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    definition_of_done TEXT NOT NULL,
    required_skill TEXT,
    required_level INTEGER CHECK (required_level BETWEEN 1 AND 4),
    owner_student_id TEXT REFERENCES student_profiles(id) ON DELETE SET NULL,
    estimated_hours REAL NOT NULL CHECK (estimated_hours BETWEEN 0.5 AND 4),
    status TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','doing','done')),
    acknowledged_skill_mismatch INTEGER NOT NULL DEFAULT 0 CHECK (acknowledged_skill_mismatch IN (0,1)),
    CHECK ((required_skill IS NULL) = (required_level IS NULL)),
    UNIQUE (milestone_id, position)
);

CREATE INDEX IF NOT EXISTS idx_profiles_session ON student_profiles(session_id);
CREATE INDEX IF NOT EXISTS idx_projects_session ON projects(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON demo_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_student_id);
PRAGMA user_version = 1;
COMMIT;
