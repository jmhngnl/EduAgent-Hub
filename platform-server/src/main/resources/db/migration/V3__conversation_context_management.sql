ALTER TABLE conversation
    ADD COLUMN context_summary LONGTEXT NULL AFTER status,
    ADD COLUMN summarized_message_count INT NOT NULL DEFAULT 0 AFTER context_summary,
    ADD COLUMN context_updated_at DATETIME(6) NULL AFTER summarized_message_count;
