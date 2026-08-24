package com.eduagent.platform.conversation.dto;

import com.eduagent.platform.conversation.Conversation;

import java.time.LocalDateTime;

public record ConversationResponse(
        String id,
        String userId,
        String workspaceId,
        String title,
        String status,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
    public static ConversationResponse from(Conversation value) {
        return new ConversationResponse(
                value.getId(), value.getUserId(), value.getWorkspaceId(), value.getTitle(),
                value.getStatus(), value.getCreatedAt(), value.getUpdatedAt()
        );
    }
}
