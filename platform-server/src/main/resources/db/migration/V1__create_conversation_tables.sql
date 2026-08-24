CREATE TABLE conversation (
    id VARCHAR(36) NOT NULL,
    user_id VARCHAR(64) NULL,
    workspace_id VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_conversation_workspace_updated (workspace_id, updated_at DESC),
    INDEX idx_conversation_user_updated (user_id, updated_at DESC),
    INDEX idx_conversation_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE chat_message (
    id VARCHAR(36) NOT NULL,
    conversation_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content MEDIUMTEXT NOT NULL,
    task_route VARCHAR(64) NULL,
    skill_name VARCHAR(128) NULL,
    tool_calls_json JSON NULL,
    citations_json JSON NULL,
    token_usage_json JSON NULL,
    latency_ms BIGINT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_chat_message_conversation_created (conversation_id, created_at, id),
    CONSTRAINT fk_chat_message_conversation
        FOREIGN KEY (conversation_id) REFERENCES conversation(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
