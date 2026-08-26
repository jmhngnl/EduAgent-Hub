CREATE TABLE app_user (
    id VARCHAR(36) NOT NULL,
    username VARCHAR(64) NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_app_user_username (username),
    INDEX idx_app_user_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE workspace (
    id VARCHAR(36) NOT NULL,
    name VARCHAR(120) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_by VARCHAR(36) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_workspace_status (status),
    CONSTRAINT fk_workspace_creator
        FOREIGN KEY (created_by) REFERENCES app_user(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE workspace_member (
    workspace_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (workspace_id, user_id),
    INDEX idx_workspace_member_user (user_id, workspace_id),
    INDEX idx_workspace_member_role (workspace_id, role),
    CONSTRAINT fk_workspace_member_workspace
        FOREIGN KEY (workspace_id) REFERENCES workspace(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_workspace_member_user
        FOREIGN KEY (user_id) REFERENCES app_user(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO workspace (id, name, status, created_by, created_at, updated_at)
VALUES ('demo', 'Demo Workspace', 'ACTIVE', NULL, NOW(6), NOW(6));
